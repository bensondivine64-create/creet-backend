from flask import Blueprint, request, jsonify, g
from cloud_storage import upload_image

from database import SessionLocal
from auth import require_auth
from serializers import user_to_dict, listing_to_dict, is_badge_verified
from geolocation import get_client_country
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
        if "country" in data:
            user.country = (data["country"] or "").strip()[:100] or None
        if "categories" in data and isinstance(data["categories"], list):
            user.categories = data["categories"][:10]
        if "onboarding_extra" in data and isinstance(data["onboarding_extra"], dict):
            user.onboarding_extra = data["onboarding_extra"]

        user.profile_completed = True

        db.commit()
        db.refresh(user)

        return jsonify(user_to_dict(user))
    except Exception:
        db.rollback()
        raise


def _connection_count(db, user_id):
    return (
        db.query(models.Connection)
        .filter(
            models.Connection.status == "accepted",
            (models.Connection.requester_id == user_id) | (models.Connection.recipient_id == user_id),
        )
        .count()
    )


@profile_bp.get("/<string:username>")
def get_public_profile(username):
    viewer_country = get_client_country()
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
            "id": user.id,
            "username": user.username,
            "full_name": user.full_name,
            "role": user.role,
            "avatar": user.avatar,
            "cover_photo": user.cover_photo,
            "bio": user.bio,
            "location": user.location,
            "categories": user.categories or [],
            "is_verified": bool(user.is_verified),
            "is_premium": bool(user.is_premium),
            "verified_badge": is_badge_verified(user),
            "connection_count": _connection_count(db, user.id),
            "created_at": user.created_at.isoformat() if user.created_at else None,
            "listings": [listing_to_dict(l, user, viewer_country=viewer_country) for l in listings],
        })
    finally:
        db.close()


ALLOWED_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}


def _allowed_image(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_IMAGE_EXTENSIONS


@profile_bp.post("/avatar")
@require_auth
def upload_avatar():
    db = g.db
    user = g.current_user

    f = request.files.get("avatar")
    if not f or not f.filename:
        return jsonify({"detail": "No image provided"}), 422
    if not _allowed_image(f.filename):
        return jsonify({"detail": "Allowed formats: jpg, jpeg, png, webp"}), 422

    user.avatar = upload_image(f, folder="creet/avatars")
    db.commit()
    db.refresh(user)

    return jsonify(user_to_dict(user))


@profile_bp.post("/cover")
@require_auth
def upload_cover():
    db = g.db
    user = g.current_user

    f = request.files.get("cover")
    if not f or not f.filename:
        return jsonify({"detail": "No image provided"}), 422
    if not _allowed_image(f.filename):
        return jsonify({"detail": "Allowed formats: jpg, jpeg, png, webp"}), 422

    user.cover_photo = upload_image(f, folder="creet/covers")
    db.commit()
    db.refresh(user)

    return jsonify(user_to_dict(user))


@profile_bp.get("/directory/<string:role>")
def get_profile_directory(role):
    if role not in ("freelancer", "vendor", "buyer"):
        return jsonify({"detail": "Invalid role"}), 422

    limit = min(int(request.args.get("limit", 10)), 30)

    db = SessionLocal()
    try:
        users = (
            db.query(models.User)
            .filter(models.User.role == role, models.User.profile_completed == True)  # noqa: E712
            .order_by(models.User.is_verified.desc(), models.User.created_at.desc())
            .limit(limit)
            .all()
        )
        return jsonify({
            "profiles": [
                {
                    "username": u.username,
                    "full_name": u.full_name,
                    "avatar": u.avatar,
                    "bio": u.bio,
                    "location": u.location,
                    "verified_badge": is_badge_verified(u),
                }
                for u in users
            ]
        })
    finally:
        db.close()
