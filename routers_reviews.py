from flask import Blueprint, request, jsonify, g
from sqlalchemy import func

import models
from database import SessionLocal
from auth import require_auth

reviews_bp = Blueprint("reviews", __name__, url_prefix="/api/listings")


def _review_to_dict(r, reviewer):
    return {
        "id": r.id,
        "rating": r.rating,
        "comment": r.comment,
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "reviewer": {
            "username": reviewer.username,
            "full_name": reviewer.full_name,
            "avatar": reviewer.avatar,
        },
    }


def _recalculate_rating(db, listing_id):
    result = db.query(
        func.avg(models.Review.rating), func.count(models.Review.id)
    ).filter(models.Review.listing_id == listing_id).first()
    avg, count = result[0] or 0, result[1] or 0
    listing = db.query(models.Listing).filter(models.Listing.id == listing_id).first()
    if listing:
        listing.rating_avg = round(float(avg), 2)
        listing.rating_count = count
        db.commit()


@reviews_bp.get("/<int:listing_id>/reviews")
def get_reviews(listing_id):
    db = SessionLocal()
    try:
        rows = (
            db.query(models.Review)
            .filter(models.Review.listing_id == listing_id)
            .order_by(models.Review.created_at.desc())
            .all()
        )
        results = []
        for r in rows:
            reviewer = db.query(models.User).filter(models.User.id == r.reviewer_id).first()
            if reviewer:
                results.append(_review_to_dict(r, reviewer))
        return jsonify({"reviews": results})
    finally:
        db.close()


@reviews_bp.post("/<int:listing_id>/reviews")
@require_auth
def create_review(listing_id):
    db = g.db
    user = g.current_user

    listing = db.query(models.Listing).filter(models.Listing.id == listing_id).first()
    if not listing:
        return jsonify({"detail": "Listing not found"}), 404
    if listing.seller_id == user.id:
        return jsonify({"detail": "You can't review your own listing"}), 403

    existing = (
        db.query(models.Review)
        .filter(models.Review.listing_id == listing_id, models.Review.reviewer_id == user.id)
        .first()
    )
    if existing:
        return jsonify({"detail": "You've already reviewed this listing"}), 409

    data = request.get_json(force=True) or {}
    rating = data.get("rating")
    if not isinstance(rating, int) or rating < 1 or rating > 5:
        return jsonify({"detail": "Rating must be a whole number from 1 to 5"}), 422

    comment = (data.get("comment") or "").strip()[:1000] or None

    review = models.Review(listing_id=listing_id, reviewer_id=user.id, rating=rating, comment=comment)
    db.add(review)
    db.commit()
    db.refresh(review)

    _recalculate_rating(db, listing_id)

    return jsonify({"success": True, "review": _review_to_dict(review, user)})
