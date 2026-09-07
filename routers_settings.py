from flask import Blueprint, jsonify, g, request

import models
from database import SessionLocal
from auth import require_auth, require_admin

settings_bp = Blueprint("settings", __name__, url_prefix="/api/settings")


def _get_settings(db):
    settings = db.query(models.SiteSettings).first()
    if not settings:
        settings = models.SiteSettings(maintenance_mode=False, banner_active=False)
        db.add(settings)
        db.commit()
        db.refresh(settings)
    return settings


def _settings_to_dict(s):
    return {
        "maintenance_mode": bool(s.maintenance_mode),
        "banner_active": bool(s.banner_active),
        "banner_text": s.banner_text,
    }


@settings_bp.get("")
def get_public_settings():
    db = SessionLocal()
    try:
        settings = _get_settings(db)
        return jsonify(_settings_to_dict(settings))
    finally:
        db.close()


@settings_bp.put("/admin")
@require_auth
@require_admin
def update_settings():
    db = g.db
    settings = _get_settings(db)
    data = request.get_json(force=True) or {}

    if "maintenance_mode" in data:
        settings.maintenance_mode = bool(data["maintenance_mode"])
    if "banner_active" in data:
        settings.banner_active = bool(data["banner_active"])
    if "banner_text" in data:
        settings.banner_text = (data.get("banner_text") or "").strip() or None

    db.commit()
    return jsonify(_settings_to_dict(settings))
