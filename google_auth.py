import os
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from dotenv import load_dotenv

load_dotenv()

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")


def verify_google_token(token: str):
    try:
        info = id_token.verify_oauth2_token(token, google_requests.Request(), GOOGLE_CLIENT_ID)
        return {
            "email": info.get("email"),
            "full_name": info.get("name") or info.get("email", "").split("@")[0],
            "email_verified": info.get("email_verified", False),
        }
    except Exception:
        return None
