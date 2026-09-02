from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

import models
import schemas
from database import get_db
from auth import hash_password, verify_password, create_token, generate_otp, get_current_user
from email_util import send_email
from recaptcha import verify_recaptcha

router = APIRouter(prefix="/api/auth", tags=["auth"])

VALID_SIGNUP_ROLES = {"buyer", "freelancer", "vendor"}
OTP_EXPIRE_MINUTES = 10
MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_MINUTES = 15


@router.post("/signup", response_model=schemas.SignupResponse)
def signup(data: schemas.SignupRequest, db: Session = Depends(get_db)):
    if not verify_recaptcha(data.recaptcha_token):
        raise HTTPException(status_code=400, detail="reCAPTCHA verification failed")
    if data.role not in VALID_SIGNUP_ROLES:
        raise HTTPException(status_code=400, detail="Invalid role")
    if db.query(models.User).filter(models.User.email == data.email).first():
        raise HTTPException(status_code=409, detail="An account already uses this email")
    if db.query(models.User).filter(models.User.username == data.username).first():
        raise HTTPException(status_code=409, detail="That username is taken")

    import os
    primary_admin_email = os.getenv("PRIMARY_ADMIN_EMAIL", "").strip().lower()
    is_primary_admin = data.email.strip().lower() == primary_admin_email

    user = models.User(
        username=data.username,
        email=data.email,
        password_hash=hash_password(data.password),
        full_name=data.full_name,
        role="admin" if is_primary_admin else data.role,
        is_verified=is_primary_admin,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    if not is_primary_admin:
        code = generate_otp()
        otp = models.OtpCode(
            email=data.email,
            code=code,
            purpose="verify",
            expires_at=datetime.utcnow() + timedelta(minutes=OTP_EXPIRE_MINUTES),
        )
        db.add(otp)
        db.commit()
        send_email(data.email, "Verify your CREET account", f"Your verification code is: {code}")

    return {"success": True, "message": "Check your email to verify your account.", "email": data.email}


@router.post("/login", response_model=schemas.AuthResponse)
def login(data: schemas.LoginRequest, db: Session = Depends(get_db)):
    if not verify_recaptcha(data.recaptcha_token):
        raise HTTPException(status_code=400, detail="reCAPTCHA verification failed")

    user = db.query(models.User).filter(models.User.email == data.email).first()
    if not user:
        raise HTTPException(status_code=401, detail="Incorrect email or password")

    if user.locked_until and user.locked_until > datetime.utcnow():
        raise HTTPException(status_code=429, detail="Too many failed attempts. Try again later.")

    if not verify_password(data.password, user.password_hash):
        user.failed_login_attempts = (user.failed_login_attempts or 0) + 1
        if user.failed_login_attempts >= MAX_LOGIN_ATTEMPTS:
            user.locked_until = datetime.utcnow() + timedelta(minutes=LOCKOUT_MINUTES)
        db.commit()
        raise HTTPException(status_code=401, detail="Incorrect email or password")

    if not user.is_verified:
        raise HTTPException(status_code=403, detail="Account not verified — check your email")

    user.failed_login_attempts = 0
    user.locked_until = None
    db.commit()

    token = create_token(user.id, user.role)
    return {"access_token": token, "user": user}


@router.get("/me", response_model=schemas.UserOut)
def get_me(user: models.User = Depends(get_current_user)):
    return user


@router.post("/verify-otp", response_model=schemas.AuthResponse)
def verify_otp(data: schemas.OtpVerifyRequest, db: Session = Depends(get_db)):
    otp = (
        db.query(models.OtpCode)
        .filter(
            models.OtpCode.email == data.email,
            models.OtpCode.code == data.code,
            models.OtpCode.purpose == "verify",
            models.OtpCode.used == False,  # noqa: E712
            models.OtpCode.expires_at > datetime.utcnow(),
        )
        .first()
    )
    if not otp:
        raise HTTPException(status_code=400, detail="Invalid or expired code")

    user = db.query(models.User).filter(models.User.email == data.email).first()
    if not user:
        raise HTTPException(status_code=404, detail="Account not found")

    user.is_verified = True
    otp.used = True
    db.commit()

    token = create_token(user.id, user.role)
    return {"access_token": token, "user": user}


@router.post("/resend-otp", response_model=schemas.SimpleSuccess)
def resend_otp(data: schemas.ResendOtpRequest, db: Session = Depends(get_db)):
    code = generate_otp()
    otp = models.OtpCode(
        email=data.email,
        code=code,
        purpose="verify",
        expires_at=datetime.utcnow() + timedelta(minutes=OTP_EXPIRE_MINUTES),
    )
    db.add(otp)
    db.commit()
    send_email(data.email, "Your CREET verification code", f"Your verification code is: {code}")
    return {"success": True}


@router.post("/forgot-password", response_model=schemas.SimpleSuccess)
def forgot_password(data: schemas.ForgotPasswordRequest, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == data.email).first()
    if user:
        code = generate_otp()
        otp = models.OtpCode(
            email=data.email,
            code=code,
            purpose="reset",
            expires_at=datetime.utcnow() + timedelta(minutes=OTP_EXPIRE_MINUTES),
        )
        db.add(otp)
        db.commit()
        send_email(data.email, "Reset your CREET password", f"Your reset code is: {code}")
    return {"success": True, "message": "If that email has an account, a reset code is on its way."}


@router.post("/reset-password", response_model=schemas.SimpleSuccess)
def reset_password(data: schemas.ResetPasswordRequest, db: Session = Depends(get_db)):
    otp = (
        db.query(models.OtpCode)
        .filter(
            models.OtpCode.email == data.email,
            models.OtpCode.code == data.code,
            models.OtpCode.purpose == "reset",
            models.OtpCode.used == False,  # noqa: E712
            models.OtpCode.expires_at > datetime.utcnow(),
        )
        .first()
    )
    if not otp:
        raise HTTPException(status_code=400, detail="Invalid or expired code")

    user = db.query(models.User).filter(models.User.email == data.email).first()
    if not user:
        raise HTTPException(status_code=404, detail="Account not found")

    user.password_hash = hash_password(data.new_password)
    otp.used = True
    db.commit()
    return {"success": True, "message": "Password updated"}
