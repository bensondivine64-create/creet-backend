import os
import threading
import requests
from dotenv import load_dotenv

load_dotenv()

RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
RESEND_FROM_EMAIL = os.getenv("RESEND_FROM_EMAIL", "CREET <hello@creet.name.ng>")


def _send_now(to: str, subject: str, body: str, html: str = None):
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


def send_email(to: str, subject: str, body: str, html: str = None):
    """Fire-and-forget: the actual network call to Resend runs on a background
    thread so callers (signup, OTP resend, password reset, etc.) don't block
    the HTTP response waiting on an external API round trip."""
    thread = threading.Thread(target=_send_now, args=(to, subject, body, html), daemon=True)
    thread.start()
