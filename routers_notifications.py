from flask import Blueprint, jsonify, g

import models
from database import SessionLocal
from auth import require_auth
from serializers import notification_to_dict

notifications_bp = Blueprint("notifications", __name__, url_prefix="/api/notifications")


@notifications_bp.get("")
@require_auth
def get_notifications():
    db = SessionLocal()
    try:
        rows = (
            db.query(models.Notification)
            .filter(models.Notification.user_id == g.current_user.id)
            .order_by(models.Notification.created_at.desc())
            .limit(50)
            .all()
        )
        unread_count = (
            db.query(models.Notification)
            .filter(models.Notification.user_id == g.current_user.id, models.Notification.is_read == False)  # noqa: E712
            .count()
        )
        return jsonify({
            "notifications": [notification_to_dict(n) for n in rows],
            "unread_count": unread_count,
        })
    finally:
        db.close()


@notifications_bp.post("/<int:notif_id>/read")
@require_auth
def mark_read(notif_id):
    db = SessionLocal()
    try:
        n = db.query(models.Notification).filter(
            models.Notification.id == notif_id, models.Notification.user_id == g.current_user.id
        ).first()
        if not n:
            return jsonify({"detail": "Notification not found"}), 404
        n.is_read = True
        db.commit()
        return jsonify({"success": True})
    finally:
        db.close()


@notifications_bp.post("/read-all")
@require_auth
def mark_all_read():
    db = SessionLocal()
    try:
        db.query(models.Notification).filter(
            models.Notification.user_id == g.current_user.id, models.Notification.is_read == False  # noqa: E712
        ).update({"is_read": True})
        db.commit()
        return jsonify({"success": True})
    finally:
        db.close()
