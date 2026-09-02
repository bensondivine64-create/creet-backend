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


def require_auth(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return jsonify({"detail": "Invalid session"}), 401
        payload = decode_token(auth_header.split(" ", 1)[1])
        if not payload:
            return jsonify({"detail": "Invalid session"}), 401

        db = SessionLocal()
        try:
            user = db.query(models.User).filter(models.User.id == int(payload["sub"])).first()
            if not user:
                return jsonify({"detail": "Account not found"}), 401
            g.current_user = user
            g.db = db
            return fn(*args, **kwargs)
        finally:
            db.close()

    return wrapper


def require_admin(fn):
    from functools import wraps

    @wraps(fn)
    def wrapper(*args, **kwargs):
        from flask import jsonify
        if not getattr(g, "current_user", None) or not g.current_user.is_admin:
            return jsonify({"detail": "Admin access required"}), 403
        return fn(*args, **kwargs)

    return wrapper
