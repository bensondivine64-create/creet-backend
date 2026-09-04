from flask import Blueprint, jsonify

import models
from database import SessionLocal
from serializers import listing_to_dict

sellers_bp = Blueprint("sellers", __name__, url_prefix="/api/sellers")


@sellers_bp.get("/<username>")
def get_seller(username):
    db = SessionLocal()
    try:
        user = db.query(models.User).filter(models.User.username == username).first()
        if not user:
            return jsonify({"detail": "This profile doesn't exist"}), 404

        listings = (
            db.query(models.Listing)
            .filter(models.Listing.seller_id == user.id, models.Listing.status == "active")
            .order_by(models.Listing.created_at.desc())
            .all()
        )

        return jsonify({
            "username": user.username,
            "full_name": user.full_name,
            "avatar": user.avatar,
            "bio": user.bio,
            "location": user.location,
            "role": user.role,
            "verified": bool(user.is_verified),
            "premium": bool(user.is_premium),
            "categories": user.categories or [],
            "listings": [listing_to_dict(l, user) for l in listings],
        })
    finally:
        db.close()
