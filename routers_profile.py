from flask import Blueprint, request, jsonify, g

from database import SessionLocal
from auth import require_auth
from serializers import user_to_dict

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
