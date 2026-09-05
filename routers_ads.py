from flask import Blueprint, request, jsonify, g
from cloud_storage import upload_image

import models
from database import SessionLocal
from auth import require_auth, require_admin

ads_bp = Blueprint("ads", __name__, url_prefix="/api/ads")


@ads_bp.get("")
def get_ads():
    db = SessionLocal()
    try:
        rows = (
            db.query(models.Ad)
            .filter(models.Ad.is_active == True)  # noqa: E712
            .order_by(models.Ad.position.asc(), models.Ad.created_at.desc())
            .all()
        )
        return jsonify({
            "ads": [
                {
                    "id": a.id,
                    "title": a.title,
                    "image_url": a.image_url,
                    "link_url": a.link_url,
                }
                for a in rows
            ]
        })
    finally:
        db.close()


@ads_bp.get("/admin")
@require_auth
@require_admin
def get_ads_admin():
    db = SessionLocal()
    try:
        rows = db.query(models.Ad).order_by(models.Ad.position.asc(), models.Ad.created_at.desc()).all()
        return jsonify({
            "ads": [
                {
                    "id": a.id,
                    "title": a.title,
                    "image_url": a.image_url,
                    "link_url": a.link_url,
                    "position": a.position,
                    "is_active": bool(a.is_active),
                }
                for a in rows
            ]
        })
    finally:
        db.close()


@ads_bp.post("")
@require_auth
@require_admin
def create_ad():
    db = g.db
    data = request.get_json(force=True) or {}

    title = (data.get("title") or "").strip()
    image_url = (data.get("image_url") or "").strip()
    if not title or not image_url:
        return jsonify({"detail": "Title and image are required"}), 422

    ad = models.Ad(
        title=title[:255],
        image_url=image_url,
        link_url=(data.get("link_url") or "").strip() or None,
        position=data.get("position", 0),
        is_active=data.get("is_active", True),
    )
    db.add(ad)
    db.commit()
    db.refresh(ad)
    return jsonify({"success": True, "id": ad.id})


@ads_bp.put("/<int:ad_id>")
@require_auth
@require_admin
def update_ad(ad_id):
    db = g.db
    ad = db.query(models.Ad).filter(models.Ad.id == ad_id).first()
    if not ad:
        return jsonify({"detail": "Ad not found"}), 404

    data = request.get_json(force=True) or {}
    if "title" in data and data["title"]:
        ad.title = data["title"][:255]
    if "image_url" in data and data["image_url"]:
        ad.image_url = data["image_url"]
    if "link_url" in data:
        ad.link_url = (data.get("link_url") or "").strip() or None
    if "position" in data:
        ad.position = data.get("position", 0)
    if "is_active" in data:
        ad.is_active = bool(data["is_active"])

    db.commit()
    return jsonify({"success": True})


@ads_bp.delete("/<int:ad_id>")
@require_auth
@require_admin
def delete_ad(ad_id):
    db = g.db
    ad = db.query(models.Ad).filter(models.Ad.id == ad_id).first()
    if not ad:
        return jsonify({"detail": "Ad not found"}), 404
    db.delete(ad)
    db.commit()
    return jsonify({"success": True})


@ads_bp.post("/upload-image")
@require_auth
@require_admin
def upload_ad_image():
    f = request.files.get("image")
    if not f or not f.filename:
        return jsonify({"detail": "No image provided"}), 422
    url = upload_image(f, folder="creet/ads")
    return jsonify({"url": url})
