from flask import Blueprint, request, jsonify, g

import models
from database import SessionLocal
from auth import require_auth
from serializers import comment_to_dict

comments_bp = Blueprint("comments", __name__, url_prefix="/api/listings")


@comments_bp.get("/<int:listing_id>/comments")
def get_comments(listing_id):
    db = SessionLocal()
    try:
        rows = (
            db.query(models.Comment)
            .filter(models.Comment.listing_id == listing_id)
            .order_by(models.Comment.created_at.desc())
            .all()
        )
        results = []
        for c in rows:
            author = db.query(models.User).filter(models.User.id == c.author_id).first()
            if author:
                results.append(comment_to_dict(c, author))
        return jsonify({"comments": results, "total": len(results)})
    finally:
        db.close()


@comments_bp.post("/<int:listing_id>/comments")
@require_auth
def post_comment(listing_id):
    data = request.get_json(force=True) or {}
    content = (data.get("content") or "").strip()
    if not content:
        return jsonify({"detail": "Comment cannot be empty"}), 422

    db = SessionLocal()
    try:
        listing = db.query(models.Listing).filter(models.Listing.id == listing_id).first()
        if not listing:
            return jsonify({"detail": "This listing doesn't exist"}), 404

        comment = models.Comment(listing_id=listing_id, author_id=g.current_user.id, content=content)
        db.add(comment)

        if listing.seller_id != g.current_user.id:
            notif = models.Notification(
                user_id=listing.seller_id,
                type="reply",
                title="New comment on your listing",
                body=f"{g.current_user.full_name} commented: \"{content[:80]}\"",
                link=f"/listing/{listing_id}",
            )
            db.add(notif)

        db.commit()
        db.refresh(comment)
        return jsonify({"success": True, "comment": comment_to_dict(comment, g.current_user)})
    finally:
        db.close()
