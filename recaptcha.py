import os
import requests
from dotenv import load_dotenv

load_dotenv()

RECAPTCHA_SECRET_KEY = os.getenv("RECAPTCHA_SECRET_KEY", "")


def verify_recaptcha(token: str) -> bool:
    if not RECAPTCHA_SECRET_KEY:
        print("[DEV MODE] Skipping reCAPTCHA verification (no secret key set)")
        return True
    if not token:
        return False
    try:
        r = requests.post(
            "https://www.google.com/recaptcha/api/siteverify",
            data={"secret": RECAPTCHA_SECRET_KEY, "response": token},
            timeout=10,
        )
        return r.json().get("success", False)
    except requests.RequestException:
        return False
