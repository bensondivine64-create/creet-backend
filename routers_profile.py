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

    db = SessionLocal()
    try:
        user = g.current_user

        if "bio" in data:
            user.bio = (data["bio"] or "").strip()[:1000]
        if "location" in data:
            user.location = (data["location"] or "").strip()[:255]
        if "categories" in data and isinstance(data["categories"], list):
            user.categories = data["categories"][:10]

        user.profile_completed = True

        db.merge(user)
        db.commit()
        db.refresh(user)

        return jsonify(user_to_dict(user))
    finally:
        db.close()


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
