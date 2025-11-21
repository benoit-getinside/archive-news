import imaplib
import email
from email.header import decode_header
from bs4 import BeautifulSoup
import os
import re
import mimetypes
import requests

# --- CONFIGURATION ---
GMAIL_USER = os.environ["GMAIL_USER"]
GMAIL_PASSWORD = os.environ["GMAIL_PASSWORD"]
TARGET_LABEL = "Netlify-News"
# IMPORTANT : Pour GitHub Pages, on utilise souvent le dossier 'docs'
OUTPUT_FOLDER = "docs"

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

def clean_filename(text):
    s = re.sub(r'[\\/*?:"<>|]', "", text)
    return s.replace(" ", "_")[:50]

def create_landing_page():
    # Crée une page d'accueil neutre pour éviter l'erreur 404
    # Mais ne liste PAS les newsletters pour la confidentialité.
    index_content = """
    <!DOCTYPE html>
    <html lang="fr">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Espace Archivage</title>
        <style>
            body { font-family: sans-serif; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; background-color: #f4f4f9; color: #555; }
            .box { text-align: center; background: white; padding: 40px; border-radius: 10px; box-shadow: 0 4px 12px rgba(0,0,0,0.1); }
        </style>
    </head>
    <body>
        <div class="box">
            <h1>🔒 Espace Archivage</h1>
            <p>Cet espace est réservé au stockage des newsletters.</p>
        </div>
    </body>
    </html>
    """
    if not os.path.exists(OUTPUT_FOLDER):
        os.makedirs(OUTPUT_FOLDER)
        
    with open(f"{OUTPUT_FOLDER}/index.html", "w", encoding='utf-8') as f:
        f.write(index_content)
    print("Page d'accueil neutre générée.")

def process_emails():
    try:
        if not os.path.exists(OUTPUT_FOLDER):
            os.makedirs(OUTPUT_FOLDER)

        # On s'assure que la page d'accueil existe toujours
        create_landing_page()

        print("Connexion au serveur...")
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(GMAIL_USER, GMAIL_PASSWORD)
        mail.select(TARGET_LABEL)
        
        status, messages = mail.search(None, 'UNSEEN')
        
        if messages[0]:
            for num in messages[0].split():
                status, msg_data = mail.fetch(num, "(RFC822)")
                msg = email.message_from_bytes(msg_data[0][1])
                
                # --- SUJET ---
                subject_header = msg["Subject"]
                if subject_header:
                    decoded_list = decode_header(subject_header)
                    subject, encoding = decoded_list[0]
                    if isinstance(subject, bytes):
                        subject = subject.decode(encoding if encoding else "utf-8")
                else:
                    subject = "Sans Titre"
                
                safe_subject = clean_filename(subject)
                print(f"Traitement de : {subject}")

                # --- CONTENU ---
                html_content = ""
                for part in msg.walk():
                    content_type = part.get_content_type()
                    content_disposition = str(part.get("Content-Disposition"))
                    if content_type == "text/html" and "attachment" not in content_disposition:
                        html_content = part.get_payload(decode=True).decode(part.get_content_charset() or 'utf-8')
                        break
                
                if not html_content and not msg.is_multipart():
                    html_content = msg.get_payload(decode=True).decode(msg.get_content_charset() or 'utf-8')

                if not html_content: continue

                # --- IMAGES ---
                soup = BeautifulSoup(html_content, "html.parser")
                
                for s in soup(["script", "iframe", "object"]):
                    s.extract()

                img_counter = 0
                for img in soup.find_all("img"):
                    src = img.get("src")
                    if not src or src.startswith("data:") or src.startswith("cid:"):
                        continue

                    try:
                        if src.startswith("//"): src = "https:" + src
                        
                        response = requests.get(src, headers=HEADERS, timeout=10)
                        if response.status_code == 200:
                            content_type = response.headers.get('content-type')
                            ext = mimetypes.guess_extension(content_type) or ".jpg"
                            img_name = f"{safe_subject}_img_{img_counter}{ext}"
                            img_path = os.path.join(OUTPUT_FOLDER, img_name)
                            
                            with open(img_path, "wb") as f:
                                f.write(response.content)
                            
                            img['src'] = img_name
                            if img.has_attr('srcset'): del img['srcset']
                            img_counter += 1
                    except Exception:
                        pass # On ignore les erreurs d'image pour ne pas bloquer

                # --- SAUVEGARDE ---
                filename = f"{OUTPUT_FOLDER}/{safe_subject}.html"
                with open(filename, "w", encoding='utf-8') as f:
                    f.write(str(soup))
                    
            print("Traitement terminé.")
        else:
            print("Aucun nouvel email.")

        mail.close()
        mail.logout()

    except Exception as e:
        print(f"Erreur: {e}")
        raise e

if __name__ == "__main__":
    process_emails()
