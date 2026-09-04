import os
import uuid
from flask import Blueprint, request, jsonify, g

from database import SessionLocal
from auth import require_auth
from serializers import user_to_dict, listing_to_dict
import models

profile_bp = Blueprint("profile", __name__, url_prefix="/api/profile")


@profile_bp.put("")
@require_auth
def update_profile():
    data = request.get_json(force=True) or {}
    db = g.db
    user = g.current_user

    try:
        if "full_name" in data:
            full_name = (data["full_name"] or "").strip()[:255]
            if not full_name:
                return jsonify({"detail": "Full name can't be empty"}), 422
            user.full_name = full_name

        if "username" in data:
            new_username = (data["username"] or "").strip().lower()[:50]
            if len(new_username) < 3:
                return jsonify({"detail": "Username must be at least 3 characters"}), 422
            if new_username != user.username:
                exists = (
                    db.query(models.User)
                    .filter(models.User.username == new_username, models.User.id != user.id)
                    .first()
                )
                if exists:
                    return jsonify({"detail": "That username is taken"}), 409
                user.username = new_username

        if "bio" in data:
            user.bio = (data["bio"] or "").strip()[:1000]
        if "location" in data:
            user.location = (data["location"] or "").strip()[:255]
        if "categories" in data and isinstance(data["categories"], list):
            user.categories = data["categories"][:10]

        user.profile_completed = True

        db.commit()
        db.refresh(user)

        return jsonify(user_to_dict(user))
    except Exception:
        db.rollback()
        raise


@profile_bp.get("/<string:username>")
def get_public_profile(username):
    db = SessionLocal()
    try:
        user = db.query(models.User).filter(models.User.username == username).first()
        if not user:
            return jsonify({"detail": "User not found"}), 404

        listings = (
            db.query(models.Listing)
            .filter(models.Listing.seller_id == user.id, models.Listing.status == "active")
            .order_by(models.Listing.created_at.desc())
            .all()
        )

        return jsonify({
            "username": user.username,
            "full_name": user.full_name,
            "role": user.role,
            "avatar": user.avatar,
            "bio": user.bio,
            "location": user.location,
            "categories": user.categories or [],
            "is_verified": bool(user.is_verified),
            "is_premium": bool(user.is_premium),
            "created_at": user.created_at.isoformat() if user.created_at else None,
            "listings": [listing_to_dict(l, user) for l in listings],
        })
    finally:
        db.close()


ALLOWED_AVATAR_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}
AVATAR_UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "static", "uploads", "avatars")


def _allowed_avatar(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_AVATAR_EXTENSIONS


@profile_bp.post("/avatar")
@require_auth
def upload_avatar():
    db = g.db
    user = g.current_user

    f = request.files.get("avatar")
    if not f or not f.filename:
        return jsonify({"detail": "No image provided"}), 422
    if not _allowed_avatar(f.filename):
        return jsonify({"detail": "Allowed formats: jpg, jpeg, png, webp"}), 422

    os.makedirs(AVATAR_UPLOAD_DIR, exist_ok=True)
    ext = f.filename.rsplit(".", 1)[1].lower()
    unique_name = f"{uuid.uuid4().hex}.{ext}"
    f.save(os.path.join(AVATAR_UPLOAD_DIR, unique_name))

    user.avatar = f"/static/uploads/avatars/{unique_name}"
    db.commit()
    db.refresh(user)

    return jsonify(user_to_dict(user))
