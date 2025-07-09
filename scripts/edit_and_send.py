import os
import logging
import json
import base64
from PyPDF2 import PdfReader
from email.message import EmailMessage
from google.oauth2 import service_account
from googleapiclient.discovery import build


# ───── Logging Setup ─────
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# ───── Gmail API Auth Setup ─────
SERVICE_ACCOUNT_FILE = os.getenv("GSA_CREDENTIALS")
GMAIL_SENDER = os.getenv("GMAIL_SENDER") 

SCOPES = ["https://www.googleapis.com/auth/gmail.send"]

creds = service_account.Credentials.from_service_account_file(
    SERVICE_ACCOUNT_FILE, scopes=SCOPES
)
delegated_creds = creds.with_subject(GMAIL_SENDER)
service = build("gmail", "v1", credentials=delegated_creds)

# ───── Email Mapping ─────
# Load email mapping from GitHub secret
encoded_map = os.getenv("EMAIL_MAP_BASE64")
email_map = {}

if encoded_map:
    try:
        decoded = base64.b64decode(encoded_map).decode("utf-8")
        email_map = json.loads(decoded)
    except Exception as e:
        raise RuntimeError(f"Failed to load email_map: {e}")
else:
    raise ValueError("EMAIL_MAP_BASE64 environment variable not set.")

# ───── Constants ─────
pdf_folder = '/home/runner/work/convenio/convenio/'
text_to_check = "Nenhum relatório encontrado para os filtros selecionados"
remaining_files = []

# ───── PDF Filtering ─────
for filename in os.listdir(pdf_folder):
    if filename.endswith(".pdf") and filename.startswith("filial"):
        pdf_path = os.path.join(pdf_folder, filename)
        try:
            reader = PdfReader(pdf_path)
            full_text = "".join(page.extract_text() or "" for page in reader.pages)

            if text_to_check in full_text:
                os.remove(pdf_path)
                logging.info(f"Deleted '{filename}' — matched filter text.")
            else:
                logging.info(f"Kept '{filename}' — report content found.")
                remaining_files.append(filename)

        except Exception as e:
            logging.error(f"Failed to read '{filename}': {e}")

# ───── Gmail API Send Emails ─────
for filename in remaining_files:
    filial_key = filename.replace(".pdf", "")
    receiver_email = email_map.get(filial_key)

    if not receiver_email:
        logging.warning(f"No email mapping found for {filial_key}. Skipping.")
        continue

    # Read the email body from file
    with open("email_body.txt", "r", encoding="utf-8") as f:
        email_body = f.read().format(filial_key=filial_key)

    # Compose Email
    msg = EmailMessage()
    msg["Subject"] = "Relatório de Convênios – Separação para Entrega"
    msg["From"] = GMAIL_SENDER
    msg["To"] = receiver_email
    # msg.set_content(f"Segue relatório teste para {filial_key}.")
    msg.set_content(email_body)

    file_path = os.path.join(pdf_folder, filename)
    try:
        with open(file_path, "rb") as f:
            file_data = f.read()
            msg.add_attachment(file_data, maintype="application", subtype="pdf", filename=filename)

        raw_message = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        send_result = service.users().messages().send(userId="me", body={"raw": raw_message}).execute()

        logging.info(f"Sent '{filename}' to {receiver_email} (message ID: {send_result['id']}).")

    except Exception as e:
        logging.error(f"Failed to send '{filename}' to {receiver_email}: {e}")

