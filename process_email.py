import imaplib
import email
from email.header import decode_header
from bs4 import BeautifulSoup
import os
import re

# --- CONFIGURATION ---
GMAIL_USER = os.environ["GMAIL_USER"]
GMAIL_PASSWORD = os.environ["GMAIL_PASSWORD"]
TARGET_LABEL = "Netlify-News"
OUTPUT_FOLDER = "newsletters"

def clean_filename(subject):
    # Nettoie le nom du fichier pour éviter les caractères interdits
    s = re.sub(r'[\\/*?:"<>|]', "", subject)
    return s.replace(" ", "_")[:50] + ".html"

def generate_index():
    print("Mise à jour du sommaire...")
    if not os.path.exists(OUTPUT_FOLDER):
        return
        
    files = [f for f in os.listdir(OUTPUT_FOLDER) if f.endswith(".html") and f != "index.html"]
    # Tri par date de création/modification (le plus récent en haut)
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
        
        # On récupère les emails (UNSEEN pour les nouveaux, ou remplacez par None pour tout tester)
        status, messages = mail.search(None, 'UNSEEN')
        
        if messages[0]:
            for num in messages[0].split():
                status, msg_data = mail.fetch(num, "(RFC822)")
                msg = email.message_from_bytes(msg_data[0][1])
                
                # Récupération du sujet
                subject_header = msg["Subject"]
                if subject_header:
                    decoded_list = decode_header(subject_header)
                    subject, encoding = decoded_list[0]
                    if isinstance(subject, bytes):
                        subject = subject.decode(encoding if encoding else "utf-8")
                else:
                    subject = "Sans Titre"

                print(f"Traitement de : {subject}")

                # Récupération du contenu HTML brut
                html_content = ""
                if msg.is_multipart():
                    for part in msg.walk():
                        if part.get_content_type() == "text/html":
                            html_content = part.get_payload(decode=True).decode(part.get_content_charset() or 'utf-8')
                            break
                else:
                    html_content = msg.get_payload(decode=True).decode(msg.get_content_charset() or 'utf-8')

                if not html_content: 
                    print("  -> Pas de contenu HTML trouvé.")
                    continue

                # --- NOUVELLE LOGIQUE : PRÉSERVATION TOTALE ---
                soup = BeautifulSoup(html_content, "html.parser")

                # 1. On ne supprime QUE les scripts dangereux
                for s in soup(["script", "iframe", "object"]):
                    s.extract()
                
                # 2. On insère le bouton retour proprement au début du BODY
                # Le style est inline pour être sûr qu'il s'affiche bien par dessus le reste
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
                    # Si le mail est mal formé et n'a pas de body, on en crée un
                    new_body = soup.new_tag("body")
                    new_body.insert(0, back_btn_html)
                    new_body.extend(soup.contents)
                    soup.append(new_body)

                # 3. On sauvegarde le tout sans rien filtrer d'autre
                filename = f"{OUTPUT_FOLDER}/{clean_filename(subject)}"
                with open(filename, "w", encoding='utf-8') as f:
                    f.write(str(soup))
                    
            print("Traitement terminé.")
        else:
            print("Aucun nouvel email à traiter.")

        mail.close()
        mail.logout()
        
        # On met à jour l'index à la fin
        generate_index()

    except Exception as e:
        print(f"Erreur critique : {e}")
        raise e

if __name__ == "__main__":
    process_emails()
