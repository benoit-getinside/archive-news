import imaplib
import email
from email.header import decode_header
from bs4 import BeautifulSoup
import os
import re

GMAIL_USER = os.environ["GMAIL_USER"]
GMAIL_PASSWORD = os.environ["GMAIL_PASSWORD"]
TARGET_LABEL = "Netlify-News"

def clean_filename(subject):
    s = re.sub(r'[\\/*?:"<>|]', "", subject)
    return s.replace(" ", "_")[:50] + ".html" # Limite la longueur du nom

def process_emails():
    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(GMAIL_USER, GMAIL_PASSWORD)
        mail.select(TARGET_LABEL)
        
        status, messages = mail.search(None, 'UNSEEN')
        
        if not messages[0]:
            print("Rien à signaler.")
            return

        # Création sécurisée du dossier
        if not os.path.exists("newsletters"):
            os.makedirs("newsletters")

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

            soup = BeautifulSoup(html_content, "html.parser")
            for s in soup(["script", "style"]):
                s.extract()

            # On récupère le body ou la table principale
            main_content = soup.find("table")
            final_html = main_content.prettify() if main_content else soup.prettify()

            full_page = f"""<!DOCTYPE html><html><head><meta charset="UTF-8"><title>{subject}</title></head><body>{final_html}</body></html>"""

            filename = f"newsletters/{clean_filename(subject)}"
            with open(filename, "w", encoding='utf-8') as f:
                f.write(full_page)
                
        mail.close()
        mail.logout()
    except Exception as e:
        print(f"Erreur: {e}")
        raise e

if __name__ == "__main__":
    process_emails()
