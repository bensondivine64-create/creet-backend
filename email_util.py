import os
import requests
from dotenv import load_dotenv

load_dotenv()

RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
RESEND_FROM_EMAIL = os.getenv("RESEND_FROM_EMAIL", "CREET <hello@creet.name.ng>")


def send_email(to: str, subject: str, body: str, html: str = None):
    if not RESEND_API_KEY:
        print(f"\n[DEV EMAIL] To: {to}\nSubject: {subject}\n{body}\n")
        return
    payload = {"from": RESEND_FROM_EMAIL, "to": [to], "subject": subject, "text": body}
    if html:
        payload["html"] = html
    try:
        requests.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {RESEND_API_KEY}"},
            json=payload,
            timeout=10,
        )
    except requests.RequestException as e:
        print(f"[EMAIL ERROR] Could not send to {to}: {e}")
