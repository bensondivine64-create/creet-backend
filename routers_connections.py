from datetime import datetime
from flask import Blueprint, jsonify, g, request

import models
from database import SessionLocal
from auth import require_auth

connections_bp = Blueprint("connections", __name__, url_prefix="/api/connections")


def _user_brief(u):
    return {
        "id": u.id,
        "username": u.username,
        "full_name": u.full_name,
        "avatar": u.avatar,
        "role": u.role,
        "is_verified": bool(u.is_verified),
    }


@connections_bp.get("/status/<int:user_id>")
@require_auth
def get_status(user_id):
    db = g.db
    me = g.current_user.id

    conn = (
        db.query(models.Connection)
        .filter(
            ((models.Connection.requester_id == me) & (models.Connection.recipient_id == user_id))
            | ((models.Connection.requester_id == user_id) & (models.Connection.recipient_id == me))
        )
        .first()
    )
    if not conn:
        return jsonify({"status": "none"})
    if conn.status == "accepted":
        return jsonify({"status": "connected", "connection_id": conn.id})
    if conn.status == "pending" and conn.requester_id == me:
        return jsonify({"status": "pending_sent", "connection_id": conn.id})
    if conn.status == "pending" and conn.recipient_id == me:
        return jsonify({"status": "pending_received", "connection_id": conn.id})
    return jsonify({"status": "none"})


@connections_bp.post("/request/<int:user_id>")
@require_auth
def send_request(user_id):
    db = g.db
    me = g.current_user.id

    if user_id == me:
        return jsonify({"detail": "Can't connect with yourself"}), 400

    target = db.query(models.User).filter(models.User.id == user_id).first()
    if not target:
        return jsonify({"detail": "User not found"}), 404

    existing = (
        db.query(models.Connection)
        .filter(
            ((models.Connection.requester_id == me) & (models.Connection.recipient_id == user_id))
            | ((models.Connection.requester_id == user_id) & (models.Connection.recipient_id == me))
        )
        .first()
    )
    if existing:
        return jsonify({"detail": "A connection already exists or is pending"}), 409

    conn = models.Connection(requester_id=me, recipient_id=user_id, status="pending")
    db.add(conn)
    db.add(models.Notification(
        user_id=user_id, type="reply", title="New connection request",
        body=f"{g.current_user.full_name} wants to connect with you.",
        link=f"/u/{g.current_user.username}",
    ))
    db.commit()
    return jsonify({"success": True, "connection_id": conn.id})


@connections_bp.post("/<int:connection_id>/accept")
@require_auth
def accept_request(connection_id):
    db = g.db
    conn = db.query(models.Connection).filter(models.Connection.id == connection_id).first()
    if not conn:
        return jsonify({"detail": "Connection not found"}), 404
    if conn.recipient_id != g.current_user.id:
        return jsonify({"detail": "Not authorized"}), 403
    conn.status = "accepted"
    conn.responded_at = datetime.utcnow()
    db.commit()
    return jsonify({"success": True})


@connections_bp.post("/<int:connection_id>/decline")
@require_auth
def decline_request(connection_id):
    db = g.db
    conn = db.query(models.Connection).filter(models.Connection.id == connection_id).first()
    if not conn:
        return jsonify({"detail": "Connection not found"}), 404
    if conn.recipient_id != g.current_user.id and conn.requester_id != g.current_user.id:
        return jsonify({"detail": "Not authorized"}), 403
    db.delete(conn)
    db.commit()
    return jsonify({"success": True})


@connections_bp.get("/mine")
@require_auth
def list_my_connections():
    db = g.db
    me = g.current_user.id

    accepted = (
        db.query(models.Connection)
        .filter(
            models.Connection.status == "accepted",
            (models.Connection.requester_id == me) | (models.Connection.recipient_id == me),
        )
        .all()
    )
    connections = []
    for c in accepted:
        other_id = c.recipient_id if c.requester_id == me else c.requester_id
        other = db.query(models.User).filter(models.User.id == other_id).first()
        if other:
            connections.append({**_user_brief(other), "connection_id": c.id})

    incoming = (
        db.query(models.Connection)
        .filter(models.Connection.status == "pending", models.Connection.recipient_id == me)
        .all()
    )
    pending_received = []
    for c in incoming:
        requester = db.query(models.User).filter(models.User.id == c.requester_id).first()
        if requester:
            pending_received.append({**_user_brief(requester), "connection_id": c.id})

    return jsonify({"connections": connections, "pending_received": pending_received})


@connections_bp.get("/feed")
@require_auth
def get_connections_feed():
    db = g.db
    me = g.current_user.id

    accepted = (
        db.query(models.Connection)
        .filter(
            models.Connection.status == "accepted",
            (models.Connection.requester_id == me) | (models.Connection.recipient_id == me),
        )
        .all()
    )
    connection_ids = [
        (c.recipient_id if c.requester_id == me else c.requester_id) for c in accepted
    ]

    if not connection_ids:
        return jsonify({"listings": []})

    from serializers import listing_to_dict
    rows = (
        db.query(models.Listing)
        .filter(models.Listing.seller_id.in_(connection_ids), models.Listing.status == "active")
        .order_by(models.Listing.created_at.desc())
        .limit(30)
        .all()
    )
    results = []
    for row in rows:
        seller = db.query(models.User).filter(models.User.id == row.seller_id).first()
        if seller:
            results.append(listing_to_dict(row, seller))

    return jsonify({"listings": results})
