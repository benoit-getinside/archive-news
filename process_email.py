import imaplib
import email
from email.header import decode_header
from bs4 import BeautifulSoup
import os
import re

# Configuration
GMAIL_USER = os.environ["GMAIL_USER"]
GMAIL_PASSWORD = os.environ["GMAIL_PASSWORD"]
TARGET_LABEL = "Netlify-News"
OUTPUT_FOLDER = "newsletters"

def clean_filename(subject):
    s = re.sub(r'[\\/*?:"<>|]', "", subject)
    return s.replace(" ", "_")[:50] + ".html"

def generate_index():
    print("Génération du sommaire...")
    files = [f for f in os.listdir(OUTPUT_FOLDER) if f.endswith(".html") and f != "index.html"]
    # Tri par date de modification (le plus récent en haut)
    files.sort(key=lambda x: os.path.getmtime(os.path.join(OUTPUT_FOLDER, x)), reverse=True)

    links_html = ""
    for f in files:
        name_display = f.replace(".html", "").replace("_", " ")
        links_html += f'<li><a href="{f}">{name_display}</a></li>\n'

    index_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Mes Newsletters</title>
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; max-width: 800px; margin: 40px auto; padding: 20px; line-height: 1.6; background-color: #f4f4f4; }}
            .container {{ background: white; padding: 30px; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }}
            h1 {{ border-bottom: 2px solid #eaeaea; padding-bottom: 10px; color: #333; }}
            ul {{ list-style-type: none; padding: 0; }}
            li {{ margin: 10px 0; border: 1px solid #eaeaea; border-radius: 8px; transition: background 0.2s; background: white; }}
            li:hover {{ background: #f0f7ff; border-color: #0070f3; }}
            a {{ display: block; padding: 15px; text-decoration: none; color: #333; font-weight: 500; }}
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

        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(GMAIL_USER, GMAIL_PASSWORD)
        mail.select(TARGET_LABEL)
        
        # On cherche tous les emails (pas seulement UNSEEN pour ce test si besoin, sinon remettre 'UNSEEN')
        status, messages = mail.search(None, 'UNSEEN')
        
        if messages[0]:
            for num in messages[0].split():
                status, msg_data = mail.fetch(num, "(RFC822)")
                msg = email.message_from_bytes(msg_data[0][1])
                
                subject_header = msg["Subject"]
                if subject_header:
                    decoded_list = decode_header(subject_header)
                    subject, encoding = decoded_list[0]
                    if isinstance(subject, bytes):
                        subject = subject.decode(encoding if encoding else "utf-8")
                else:
                    subject = "Sans Titre"

                print(f"Traitement de : {subject}")

                html_content = ""
                if msg.is_multipart():
                    for part in msg.walk():
                        if part.get_content_type() == "text/html":
                            html_content = part.get_payload(decode=True).decode()
                            break
                else:
                    html_content = msg.get_payload(decode=True).decode()

                if not html_content: continue

                # --- CORRECTION MAJEURE : FIDÉLITÉ TOTALE ---
                soup = BeautifulSoup(html_content, "html.parser")
                
                # 1. On enlève les scripts (JS) par sécurité
                for s in soup(["script"]):
                    s.extract()

                # 2. On enlève les métadonnées de transfert Gmail (si le mail a été transféré)
                # (Ex: "De: Machin, Envoyé le: ...")
                for gmail_attr in soup.select('.gmail_attr'):
                    gmail_attr.extract()
                
                # 3. On ne cherche PAS de table spécifique. On prend TOUT le HTML.
                # On ajoute juste le bouton retour en haut.
                
                final_html = str(soup)
                
                # Ajout du bouton retour de manière "propre" sans casser la structure
                # On l'injecte juste après l'ouverture du <body>
                back_btn_html = '<a href="index.html" style="display:block; padding:10px; background:#222; color:white; text-decoration:none; font-family:sans-serif; font-size:14px; text-align:center; position:relative; z-index:9999;">← Retour au sommaire</a>'
                
                if "<body>" in final_html:
                     final_html = final_html.replace("<body>", f"<body>{back_btn_html}")
                elif "<BODY>" in final_html: # Au cas où c'est en majuscules
                     final_html = final_html.replace("<BODY>", f"<BODY>{back_btn_html}")
                else:
                    # Si pas de body (fragment HTML), on enveloppe le tout
                    final_html = f"""<!DOCTYPE html><html><head><meta charset="UTF-8"><title>{subject}</title></head><body>{back_btn_html}{final_html}</body></html>"""

                filename = f"{OUTPUT_FOLDER}/{clean_filename(subject)}"
                with open(filename, "w", encoding='utf-8') as f:
                    f.write(final_html)

            mail.close()
            mail.logout()
        else:
            print("Pas de nouveaux emails.")

        generate_index()

    except Exception as e:
        print(f"Erreur: {e}")
        raise e

if __name__ == "__main__":
    process_emails()
