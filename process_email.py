import imaplib
import email
from email.header import decode_header
from bs4 import BeautifulSoup
import os
import re
import mimetypes

# --- CONFIGURATION ---
GMAIL_USER = os.environ["GMAIL_USER"]
GMAIL_PASSWORD = os.environ["GMAIL_PASSWORD"]
TARGET_LABEL = "Netlify-News"
OUTPUT_FOLDER = "newsletters"

def clean_filename(text):
    # Nettoie le texte pour en faire un nom de fichier valide
    s = re.sub(r'[\\/*?:"<>|]', "", text)
    return s.replace(" ", "_")[:50]

def generate_index():
    print("Mise à jour du sommaire...")
    if not os.path.exists(OUTPUT_FOLDER):
        return
        
    files = [f for f in os.listdir(OUTPUT_FOLDER) if f.endswith(".html") and f != "index.html"]
    files.sort(key=lambda x: os.path.getmtime(os.path.join(OUTPUT_FOLDER, x)), reverse=True)

    links_html = ""
    for f in files:
        name_display = f.replace(".html", "").replace("_", " ")
        links_html += f'''
        <li>
            <a href="{f}">
                <span class="icon">📧</span>
                <span class="title">{name_display}</span>
            </a>
        </li>
        '''

    index_content = f"""
    <!DOCTYPE html>
    <html lang="fr">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Mes Newsletters</title>
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; background-color: #f4f4f9; margin: 0; padding: 20px; color: #333; }}
            .container {{ max-width: 800px; margin: 40px auto; background: white; padding: 40px; border-radius: 16px; box-shadow: 0 10px 25px rgba(0,0,0,0.05); }}
            h1 {{ text-align: center; color: #2c3e50; margin-bottom: 40px; font-size: 2rem; }}
            ul {{ list-style: none; padding: 0; }}
            li {{ margin-bottom: 15px; }}
            a {{ display: flex; align-items: center; padding: 20px; background: #fff; border: 1px solid #eaeaea; border-radius: 12px; text-decoration: none; color: #2c3e50; transition: all 0.2s ease; }}
            a:hover {{ transform: translateY(-2px); box-shadow: 0 5px 15px rgba(0,0,0,0.08); border-color: #0070f3; }}
            .icon {{ font-size: 1.5rem; margin-right: 15px; }}
            .title {{ font-weight: 600; font-size: 1.1rem; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>📬 Archives Newsletters</h1>
            <ul>
                {links_html}
            </ul>
        </div>
    </body>
    </html>
    """
    with open(f"{OUTPUT_FOLDER}/index.html", "w", encoding='utf-8') as f:
        f.write(index_content)

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

                # --- 2. EXTRACTION IMAGES & HTML ---
                html_content = ""
                images_cid = {} # Dictionnaire pour stocker les liens cid -> fichier local

                # On parcourt toutes les parties du mail (texte, html, images attachées)
                for part in msg.walk():
                    content_type = part.get_content_type()
                    content_disposition = str(part.get("Content-Disposition"))

                    # Si c'est le HTML
                    if content_type == "text/html" and "attachment" not in content_disposition:
                        html_content = part.get_payload(decode=True).decode(part.get_content_charset() or 'utf-8')
                    
                    # Si c'est une image
                    if "image" in content_type:
                        # On cherche l'ID de l'image (cid)
                        cid = part.get("Content-ID")
                        if cid:
                            # Nettoyage du cid (<12345> -> 12345)
                            cid_clean = cid.strip('<>')
                            
                            # Extension fichier
                            ext = mimetypes.guess_extension(content_type) or ".jpg"
                            image_filename = f"{safe_subject}_img_{cid_clean}{ext}"
                            image_filename = clean_filename(image_filename) # Sécurité nom
                            
                            # Sauvegarde de l'image sur le disque
                            filepath = os.path.join(OUTPUT_FOLDER, image_filename)
                            with open(filepath, "wb") as f:
                                f.write(part.get_payload(decode=True))
                            
                            # On mémorise : "Quand tu vois ce CID, utilise ce fichier"
                            images_cid[cid_clean] = image_filename

                if not html_content: 
                    print("  -> Pas de contenu HTML trouvé.")
                    continue

                # --- 3. TRAITEMENT DU HTML ---
                soup = BeautifulSoup(html_content, "html.parser")

                # A. Réparation des images attachées (CID)
                for img in soup.find_all("img"):
                    if img.get("src") and "cid:" in img["src"]:
                        cid_in_src = img["src"].replace("cid:", "").strip()
                        if cid_in_src in images_cid:
                            img["src"] = images_cid[cid_in_src]
                
                # B. Réparation HTTP -> HTTPS (Mixed Content Fix)
                for img in soup.find_all("img"):
                    if img.get("src") and img["src"].startswith("http://"):
                        # On tente de passer en HTTPS. 99% des serveurs modernes le supportent.
                        img["src"] = img["src"].replace("http://", "https://")

                # C. Sécurité Scripts
                for s in soup(["script", "iframe", "object"]):
                    s.extract()

                # D. Bouton Retour
                back_btn_html = BeautifulSoup('''
                <div style="background-color: #1a1a1a; color: white; padding: 10px; text-align: center; font-family: sans-serif; font-size: 14px; position: relative; z-index: 99999;">
                    <a href="index.html" style="color: white; text-decoration: none; font-weight: bold;">
                        ← Retour au sommaire
                    </a>
                </div>
                ''', 'html.parser')

                if soup.body:
                    soup.body.insert(0, back_btn_html)
                else:
                    new_body = soup.new_tag("body")
                    new_body.insert(0, back_btn_html)
                    new_body.extend(soup.contents)
                    soup.append(new_body)

                # --- 4. SAUVEGARDE ---
                filename = f"{OUTPUT_FOLDER}/{safe_subject}.html"
                with open(filename, "w", encoding='utf-8') as f:
                    f.write(str(soup))
                    
            print("Traitement terminé.")
        else:
            print("Aucun nouvel email à traiter.")

        mail.close()
        mail.logout()
        generate_index()

    except Exception as e:
        print(f"Erreur critique : {e}")
        raise e

if __name__ == "__main__":
    process_emails()
