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
OUTPUT_FOLDER = "docs"

# On se fait passer pour un navigateur pour éviter d'être bloqué par les serveurs d'images
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

def clean_filename(text):
    s = re.sub(r'[\\/*?:"<>|]', "", text)
    return s.replace(" ", "_")[:50]

def process_emails():
    try:
        if not os.path.exists(OUTPUT_FOLDER):
            os.makedirs(OUTPUT_FOLDER)

        print("Connexion au serveur...")
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(GMAIL_USER, GMAIL_PASSWORD)
        mail.select(TARGET_LABEL)
        
        status, messages = mail.search(None, 'UNSEEN')
        
        if messages[0]:
            for num in messages[0].split():
                status, msg_data = mail.fetch(num, "(RFC822)")
                msg = email.message_from_bytes(msg_data[0][1])
                
                # --- 1. TITRE ---
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

                # --- 2. EXTRACTION CONTENU ---
                html_content = ""
                
                for part in msg.walk():
                    content_type = part.get_content_type()
                    content_disposition = str(part.get("Content-Disposition"))

                    if content_type == "text/html" and "attachment" not in content_disposition:
                        html_content = part.get_payload(decode=True).decode(part.get_content_charset() or 'utf-8')
                        break # On a trouvé le HTML principal
                
                # Fallback si pas de multipart
                if not html_content and not msg.is_multipart():
                    html_content = msg.get_payload(decode=True).decode(msg.get_content_charset() or 'utf-8')

                if not html_content: 
                    print("  -> Pas de contenu HTML trouvé.")
                    continue

                # --- 3. TRAITEMENT & TÉLÉCHARGEMENT IMAGES ---
                soup = BeautifulSoup(html_content, "html.parser")

                # A. Suppression scripts dangereux
                for s in soup(["script", "iframe", "object"]):
                    s.extract()

                # B. Gestion des images (Le coeur du correctif)
                img_counter = 0
                for img in soup.find_all("img"):
                    src = img.get("src")
                    
                    if not src:
                        continue

                    # Si c'est déjà une image base64 ou cid, on passe (cid géré par ailleurs si besoin, mais ici on vise les liens http)
                    if src.startswith("data:") or src.startswith("cid:"):
                        continue

                    try:
                        # Gestion des liens relatifs protocol-less (//example.com)
                        if src.startswith("//"):
                            src = "https:" + src
                        
                        # Téléchargement
                        response = requests.get(src, headers=HEADERS, timeout=10)
                        if response.status_code == 200:
                            # Déterminer l'extension
                            content_type = response.headers.get('content-type')
                            ext = mimetypes.guess_extension(content_type) or ".jpg"
                            
                            # Nom unique pour l'image
                            img_name = f"{safe_subject}_img_{img_counter}{ext}"
                            img_path = os.path.join(OUTPUT_FOLDER, img_name)
                            
                            # Sauvegarde locale
                            with open(img_path, "wb") as f:
                                f.write(response.content)
                            
                            # Remplacement du lien dans le HTML par le fichier local
                            img['src'] = img_name
                            # On retire srcset pour forcer l'usage du src local
                            if img.has_attr('srcset'):
                                del img['srcset']
                                
                            img_counter += 1
                            print(f"  -> Image téléchargée : {src[:30]}...")
                        else:
                            print(f"  -> Échec téléchargement (Code {response.status_code}): {src[:30]}...")
                    
                    except Exception as e:
                        print(f"  -> Erreur téléchargement image : {e}")
                        # En cas d'erreur, on laisse le lien original

                # --- 4. SAUVEGARDE ---
                # On ne met PLUS le bouton retour
                filename = f"{OUTPUT_FOLDER}/{safe_subject}.html"
                with open(filename, "w", encoding='utf-8') as f:
                    f.write(str(soup))
                    
            print("Traitement terminé.")
        else:
            print("Aucun nouvel email à traiter.")

        mail.close()
        mail.logout()
        # On ne génère plus l'index pour la confidentialité (ou on le garde secret sans liens vers lui)

    except Exception as e:
        print(f"Erreur critique : {e}")
        raise e

if __name__ == "__main__":
    process_emails()
