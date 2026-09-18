import os
import re
import hashlib
import secrets
from functools import wraps
import jwt
from datetime import datetime, timedelta
from flask import request, jsonify, g
from dotenv import load_dotenv

from database import SessionLocal
import models

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me")
ALGORITHM = "HS256"
TOKEN_EXPIRE_DAYS = 7
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000)
    return f"{salt}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        salt, digest_hex = stored.split("$")
    except ValueError:
        return False
    check = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000)
    return secrets.compare_digest(check.hex(), digest_hex)


def create_token(user_id: int, role: str) -> str:
    payload = {
        "sub": str(user_id),
        "role": role,
        "exp": datetime.utcnow() + timedelta(days=TOKEN_EXPIRE_DAYS),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str):
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.PyJWTError:
        return None


def generate_otp() -> str:
    return f"{secrets.randbelow(1000000):06d}"


def is_valid_email(email: str) -> bool:
    return bool(email and EMAIL_RE.match(email))


def _extract_token():
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header.split(" ", 1)[1]
    return request.cookies.get("creet_session")


def require_auth(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        token = _extract_token()
        if not token:
            return jsonify({"detail": "Invalid session"}), 401
        payload = decode_token(token)
        if not payload:
            return jsonify({"detail": "Invalid session"}), 401

        db = SessionLocal()
        try:
            user = db.query(models.User).filter(models.User.id == int(payload["sub"])).first()
            if not user:
                return jsonify({"detail": "Account not found"}), 401
            if not user.country:
                try:
                    from geolocation import get_client_country
                    detected = get_client_country()
                    if detected:
                        user.country = detected
                        db.commit()
                except Exception:
                    pass
            now = datetime.utcnow()
            if not user.last_active or (now - user.last_active).total_seconds() > 60:
                user.last_active = now
                db.commit()

            if user.account_status == "suspended":
                if user.suspension_until and user.suspension_until <= datetime.utcnow():
                    user.account_status = "active"
                    user.suspension_type = None
                    user.suspension_until = None
                    db.commit()
                else:
                    return jsonify({"detail": "Your account has been suspended"}), 403
            g.current_user = user
            g.db = db
            return fn(*args, **kwargs)
        finally:
            db.close()

    return wrapper


def require_admin(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not getattr(g, "current_user", None) or not g.current_user.is_admin:
            return jsonify({"detail": "Admin access required"}), 403
        return fn(*args, **kwargs)

    return wrapper
