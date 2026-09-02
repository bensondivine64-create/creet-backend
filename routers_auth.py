import os
import secrets
from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify, g

import models
from database import SessionLocal
from auth import hash_password, verify_password, create_token, generate_otp, is_valid_email, require_auth
from serializers import user_to_dict
from email_util import send_email
from recaptcha import verify_recaptcha
from google_auth import verify_google_token

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")

VALID_SIGNUP_ROLES = {"buyer", "freelancer", "vendor"}
OTP_EXPIRE_MINUTES = 10
MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_MINUTES = 15


def make_unique_username(db, base: str) -> str:
    base = "".join(ch for ch in base.lower() if ch.isalnum()) or "user"
    candidate = base
    while db.query(models.User).filter(models.User.username == candidate).first():
        candidate = f"{base}{secrets.randbelow(9999)}"
    return candidate


def is_primary_admin_email(email: str) -> bool:
    primary_admin_email = os.getenv("PRIMARY_ADMIN_EMAIL", "").strip().lower()
    return bool(primary_admin_email) and email == primary_admin_email


@auth_bp.post("/signup")
def signup():
    data = request.get_json(force=True) or {}
    username = data.get("username", "").strip()
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")
    full_name = data.get("full_name", "").strip()
    role = data.get("role", "")
    recaptcha_token = data.get("recaptcha_token")

    if not verify_recaptcha(recaptcha_token):
        return jsonify({"detail": "reCAPTCHA verification failed"}), 400
    if len(username) < 3:
        return jsonify({"detail": "Username must be at least 3 characters"}), 422
    if not is_valid_email(email):
        return jsonify({"detail": "Invalid email"}), 422
    if len(password) < 8:
        return jsonify({"detail": "Password must be at least 8 characters"}), 422
    if not full_name:
        return jsonify({"detail": "Full name is required"}), 422
    if role not in VALID_SIGNUP_ROLES:
        return jsonify({"detail": "Invalid role"}), 400

    db = SessionLocal()
    try:
        if db.query(models.User).filter(models.User.email == email).first():
            return jsonify({"detail": "An account already uses this email"}), 409
        if db.query(models.User).filter(models.User.username == username).first():
            return jsonify({"detail": "That username is taken"}), 409

        is_admin = is_primary_admin_email(email)

        user = models.User(
            username=username,
            email=email,
            password_hash=hash_password(password),
            full_name=full_name,
            role=role,
            is_admin=is_admin,
            is_verified=is_admin,
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        if not is_admin:
            code = generate_otp()
            otp = models.OtpCode(
                email=email,
                code=code,
                purpose="verify",
                expires_at=datetime.utcnow() + timedelta(minutes=OTP_EXPIRE_MINUTES),
            )
            db.add(otp)
            db.commit()
            send_email(email, "Verify your CREET account", f"Your verification code is: {code}")

        return jsonify({"success": True, "message": "Check your email to verify your account.", "email": email})
    finally:
        db.close()


@auth_bp.post("/login")
def login():
    data = request.get_json(force=True) or {}
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")
    recaptcha_token = data.get("recaptcha_token")

    if not verify_recaptcha(recaptcha_token):
        return jsonify({"detail": "reCAPTCHA verification failed"}), 400

    db = SessionLocal()
    try:
        user = db.query(models.User).filter(models.User.email == email).first()
        if not user:
            return jsonify({"detail": "Incorrect email or password"}), 401

        if user.locked_until and user.locked_until > datetime.utcnow():
            return jsonify({"detail": "Too many failed attempts. Try again later."}), 429

        if not verify_password(password, user.password_hash):
            user.failed_login_attempts = (user.failed_login_attempts or 0) + 1
            if user.failed_login_attempts >= MAX_LOGIN_ATTEMPTS:
                user.locked_until = datetime.utcnow() + timedelta(minutes=LOCKOUT_MINUTES)
            db.commit()
            return jsonify({"detail": "Incorrect email or password"}), 401

        if not user.is_verified:
            return jsonify({"detail": "Account not verified — check your email"}), 403

        user.failed_login_attempts = 0
        user.locked_until = None
        db.commit()

        token = create_token(user.id, user.role)
        return jsonify({"access_token": token, "user": user_to_dict(user)})
    finally:
        db.close()


@auth_bp.post("/google")
def google_login():
    data = request.get_json(force=True) or {}
    credential = data.get("credential", "")
    role = data.get("role", "")

    info = verify_google_token(credential)
    if not info or not info.get("email_verified"):
        return jsonify({"detail": "Could not verify Google account"}), 400

    email = info["email"].lower()

    db = SessionLocal()
    try:
        user = db.query(models.User).filter(models.User.email == email).first()

        if not user:
            if role not in VALID_SIGNUP_ROLES:
                return jsonify({"detail": "Choose an account type to continue"}), 400

            is_admin = is_primary_admin_email(email)
            username = make_unique_username(db, email.split("@")[0])
            user = models.User(
                username=username,
                email=email,
                password_hash=hash_password(secrets.token_urlsafe(32)),
                full_name=info["full_name"],
                role=role,
                is_admin=is_admin,
                is_verified=True,
            )
            db.add(user)
            db.commit()
            db.refresh(user)

        token = create_token(user.id, user.role)
        return jsonify({"access_token": token, "user": user_to_dict(user)})
    finally:
        db.close()


@auth_bp.get("/me")
@require_auth
def get_me():
    return jsonify(user_to_dict(g.current_user))


@auth_bp.post("/verify-otp")
def verify_otp():
    data = request.get_json(force=True) or {}
    email = data.get("email", "").strip().lower()
    code = data.get("code", "")

    db = SessionLocal()
    try:
        otp = (
            db.query(models.OtpCode)
            .filter(
                models.OtpCode.email == email,
                models.OtpCode.code == code,
                models.OtpCode.purpose == "verify",
                models.OtpCode.used == False,  # noqa: E712
                models.OtpCode.expires_at > datetime.utcnow(),
            )
            .first()
        )
        if not otp:
            return jsonify({"detail": "Invalid or expired code"}), 400

        user = db.query(models.User).filter(models.User.email == email).first()
        if not user:
            return jsonify({"detail": "Account not found"}), 404

        user.is_verified = True
        otp.used = True
        db.commit()

        token = create_token(user.id, user.role)
        return jsonify({"access_token": token, "user": user_to_dict(user)})
    finally:
        db.close()


@auth_bp.post("/resend-otp")
def resend_otp():
    data = request.get_json(force=True) or {}
    email = data.get("email", "").strip().lower()

    db = SessionLocal()
    try:
        code = generate_otp()
        otp = models.OtpCode(
            email=email,
            code=code,
            purpose="verify",
            expires_at=datetime.utcnow() + timedelta(minutes=OTP_EXPIRE_MINUTES),
        )
        db.add(otp)
        db.commit()
        send_email(email, "Your CREET verification code", f"Your verification code is: {code}")
        return jsonify({"success": True})
    finally:
        db.close()


@auth_bp.post("/forgot-password")
def forgot_password():
    data = request.get_json(force=True) or {}
    email = data.get("email", "").strip().lower()

    db = SessionLocal()
    try:
        user = db.query(models.User).filter(models.User.email == email).first()
        if user:
            code = generate_otp()
            otp = models.OtpCode(
                email=email,
                code=code,
                purpose="reset",
                expires_at=datetime.utcnow() + timedelta(minutes=OTP_EXPIRE_MINUTES),
            )
            db.add(otp)
            db.commit()
            send_email(email, "Reset your CREET password", f"Your reset code is: {code}")
        return jsonify({"success": True, "message": "If that email has an account, a reset code is on its way."})
    finally:
        db.close()


@auth_bp.post("/reset-password")
def reset_password():
    data = request.get_json(force=True) or {}
    email = data.get("email", "").strip().lower()
    code = data.get("code", "")
    new_password = data.get("new_password", "")

    if len(new_password) < 8:
        return jsonify({"detail": "Password must be at least 8 characters"}), 422

    db = SessionLocal()
    try:
        otp = (
            db.query(models.OtpCode)
            .filter(
                models.OtpCode.email == email,
                models.OtpCode.code == code,
                models.OtpCode.purpose == "reset",
                models.OtpCode.used == False,  # noqa: E712
                models.OtpCode.expires_at > datetime.utcnow(),
            )
            .first()
        )
        if not otp:
            return jsonify({"detail": "Invalid or expired code"}), 400

        user = db.query(models.User).filter(models.User.email == email).first()
        if not user:
            return jsonify({"detail": "Account not found"}), 404

        user.password_hash = hash_password(new_password)
        otp.used = True
        db.commit()
        return jsonify({"success": True, "message": "Password updated"})
    finally:
        db.close()
