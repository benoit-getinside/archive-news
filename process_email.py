import imaplib
import email
from email.header import decode_header
from bs4 import BeautifulSoup, Tag
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
        
        # 'UNSEEN' pour les nouveaux, ou None pour tous (attention aux doublons si None)
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

                # --- CIBLAGE PRÉCIS ---
                original_soup = BeautifulSoup(html_content, "html.parser")
                
                # 1. Nettoyage (Sécurité uniquement)
                for s in original_soup(["script", "iframe", "object"]):
                    s.extract()

                # 2. Création d'une structure propre
                new_soup = BeautifulSoup("<!DOCTYPE html><html><head><meta charset='UTF-8'></head><body></body></html>", "html.parser")
                
                # Titre
                new_tag = new_soup.new_tag("title")
                new_tag.string = subject
                new_soup.head.append(new_tag)

                # 3. Récupération des styles CSS originaux (Important pour le design !)
                # On copie tous les <style> du mail original vers le nouveau
                for style in original_soup.find_all("style"):
                    new_soup.head.append(style)

                # 4. EXTRACTION DU CONTENU (Le coeur du correctif)
                # On cherche la DIV magique que vous m'avez montrée (celle qui contient tout)
                # Regex : on cherche un ID qui finit par "bodyTable" (ex: m_247...bodyTable)
                main_content = original_soup.find("div", id=re.compile(r"bodyTable$"))

                if not main_content:
                    # Fallback : Si on ne trouve pas l'ID spécifique, on prend le body entier
                    main_content = original_soup.body

                # 5. Ajout du bouton retour
                back_btn = new_soup.new_tag("a", href="index.html")
                back_btn.string = "← Retour au sommaire"
                back_btn['style'] = "display:block; padding:15px; background:#222; color:white; text-decoration:none; font-family:sans-serif; font-size:14px; text-align:center; font-weight:bold;"
                new_soup.body.append(back_btn)

                # 6. Injection du contenu
                if main_content:
                    # Si c'est le body, on prend ses enfants pour éviter d'avoir <body><body>
                    if main_content.name == 'body':
                        for child in main_content.contents:
                            new_soup.body.append(child)
                    else:
                        new_soup.body.append(main_content)

                filename = f"{OUTPUT_FOLDER}/{clean_filename(subject)}"
                with open(filename, "w", encoding='utf-8') as f:
                    f.write(str(new_soup))

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
