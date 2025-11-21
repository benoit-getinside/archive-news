import imaplib
import email
from email.header import decode_header
from bs4 import BeautifulSoup
import os
import re
import mimetypes
import requests
import datetime

# --- CONFIGURATION ---
GMAIL_USER = os.environ["GMAIL_USER"]
GMAIL_PASSWORD = os.environ["GMAIL_PASSWORD"]
TARGET_LABEL = "Netlify-News"
# On garde 'docs' pour la compatibilité GitHub Pages
OUTPUT_FOLDER = "docs"

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

def clean_filename(text):
    s = re.sub(r'[\\/*?:"<>|]', "", text)
    return s.replace(" ", "_")[:50]

def generate_index():
    print("Mise à jour du sommaire...")
    if not os.path.exists(OUTPUT_FOLDER):
        return
        
    # On récupère tous les fichiers HTML sauf index.html
    files = [f for f in os.listdir(OUTPUT_FOLDER) if f.endswith(".html") and f != "index.html"]
    
    # Tri par date de modification (le plus récent en haut)
    files.sort(key=lambda x: os.path.getmtime(os.path.join(OUTPUT_FOLDER, x)), reverse=True)

    links_html = ""
    for f in files:
        # On rend le nom plus joli pour l'affichage
        name_display = f.replace(".html", "").replace("_", " ")
        
        # On récupère la date du fichier pour l'afficher
        filepath = os.path.join(OUTPUT_FOLDER, f)
        timestamp = os.path.getmtime(filepath)
        date_str = datetime.datetime.fromtimestamp(timestamp).strftime('%d/%m/%Y')

        links_html += f'''
        <li>
            <a href="{f}">
                <div class="link-content">
                    <span class="icon">📧</span>
                    <span class="title">{name_display}</span>
                </div>
                <span class="date">{date_str}</span>
            </a>
        </li>
        '''

    index_content = f"""
    <!DOCTYPE html>
    <html lang="fr">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Archives Newsletters</title>
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; background-color: #f6f9fc; margin: 0; padding: 20px; color: #333; }}
            .container {{ max-width: 800px; margin: 40px auto; background: white; padding: 40px; border-radius: 16px; box-shadow: 0 4px 12px rgba(0,0,0,0.05); }}
            h1 {{ text-align: center; color: #1a1a1a; margin-bottom: 40px; font-size: 1.8rem; border-bottom: 2px solid #f0f0f0; padding-bottom: 20px; }}
            ul {{ list-style: none; padding: 0; }}
            li {{ margin-bottom: 12px; }}
            a {{ display: flex; justify-content: space-between; align-items: center; padding: 18px 25px; background: #fff; border: 1px solid #eaeaea; border-radius: 10px; text-decoration: none; color: #2c3e50; transition: all 0.2s ease; }}
            a:hover {{ transform: translateY(-2px); box-shadow: 0 5px 15px rgba(0,0,0,0.05); border-color: #0070f3; color: #0070f3; }}
            .link-content {{ display: flex; align-items: center; }}
            .icon {{ font-size: 1.2rem; margin-right: 15px; }}
            .title {{ font-weight: 600; font-size: 1.05rem; }}
            .date {{ font-size: 0.85rem; color: #888; background: #f4f4f4; padding: 5px 10px; border-radius: 20px; }}
            a:hover .date {{ background: #e8f0fe; color: #0070f3; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>📬 Mes Newsletters</h1>
            <ul>
                {links_html}
            </ul>
        </div>
    </body>
    </html>
    """
    
    with open(f"{OUTPUT_FOLDER}/index.html", "w", encoding='utf-8') as f:
        f.write(index_content)
    print("Sommaire généré avec succès.")

def process_emails():
    try:
        if not os.path.exists(OUTPUT_FOLDER):
            os.makedirs(OUTPUT_FOLDER)

        print("Connexion au serveur...")
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(GMAIL_USER, GMAIL_PASSWORD)
        mail.select(TARGET_LABEL)
        
        status, messages = mail.search(None, 'UNSEEN')
        
        # On traite les emails s'il y en a
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

                # --- TRAITEMENT HTML & IMAGES ---
                soup = BeautifulSoup(html_content, "html.parser")
                
                # Suppression scripts
                for s in soup(["script", "iframe", "object"]):
                    s.extract()

                # Téléchargement Images
                img_counter = 0
                for img in soup.find_all("img"):
                    src = img.get("src")
                    if not src or src.startswith("data:") or src.startswith("cid:"):
                        continue

                    try:
                        if src.startswith
