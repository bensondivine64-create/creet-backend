from flask import Blueprint, request, jsonify, g

import models
from database import SessionLocal
from auth import require_auth

messages_bp = Blueprint("messages", __name__, url_prefix="/api/conversations")


def other_user_id(conv, my_id):
    return conv.user_b_id if conv.user_a_id == my_id else conv.user_a_id


@messages_bp.get("")
@require_auth
def get_conversations():
    db = SessionLocal()
    try:
        me = g.current_user.id
        rows = (
            db.query(models.Conversation)
            .filter((models.Conversation.user_a_id == me) | (models.Conversation.user_b_id == me))
            .order_by(models.Conversation.created_at.desc())
            .all()
        )
        results = []
        for conv in rows:
            other = db.query(models.User).filter(models.User.id == other_user_id(conv, me)).first()
            if not other:
                continue
            last_msg = (
                db.query(models.Message)
                .filter(models.Message.conversation_id == conv.id)
                .order_by(models.Message.created_at.desc())
                .first()
            )
            listing_title = None
            if conv.listing_id:
                listing = db.query(models.Listing).filter(models.Listing.id == conv.listing_id).first()
                if listing:
                    listing_title = listing.title
            unread_count = 0  # basic implementation, no per-user read tracking yet
            results.append({
                "id": conv.id,
                "participant": {
                    "username": other.username,
                    "full_name": other.full_name,
                    "avatar": other.avatar,
                    "verified": bool(other.is_verified),
                },
                "listing_id": conv.listing_id,
                "listing_title": listing_title,
                "last_message": last_msg.content if last_msg else "",
                "last_message_at": last_msg.created_at.isoformat() if last_msg and last_msg.created_at else conv.created_at.isoformat(),
                "unread_count": unread_count,
            })
        return jsonify({"conversations": results})
    finally:
        db.close()


@messages_bp.post("")
@require_auth
def start_conversation():
    data = request.get_json(force=True) or {}
    listing_id = data.get("listing_id")
    if not listing_id:
        return jsonify({"detail": "listing_id is required"}), 422

    db = SessionLocal()
    try:
        listing = db.query(models.Listing).filter(models.Listing.id == listing_id).first()
        if not listing:
            return jsonify({"detail": "This listing doesn't exist"}), 404

        me = g.current_user.id
        seller_id = listing.seller_id
        if seller_id == me:
            return jsonify({"detail": "You can't message yourself"}), 400

        existing = (
            db.query(models.Conversation)
            .filter(
                models.Conversation.listing_id == listing_id,
                ((models.Conversation.user_a_id == me) & (models.Conversation.user_b_id == seller_id))
                | ((models.Conversation.user_a_id == seller_id) & (models.Conversation.user_b_id == me)),
            )
            .first()
        )
        if existing:
            return jsonify({"conversation_id": existing.id})

        conv = models.Conversation(user_a_id=me, user_b_id=seller_id, listing_id=listing_id)
        db.add(conv)
        db.commit()
        db.refresh(conv)
        return jsonify({"conversation_id": conv.id})
    finally:
        db.close()


@messages_bp.get("/<int:conv_id>/messages")
@require_auth
def get_messages(conv_id):
    db = SessionLocal()
    try:
        conv = db.query(models.Conversation).filter(models.Conversation.id == conv_id).first()
        if not conv or g.current_user.id not in (conv.user_a_id, conv.user_b_id):
            return jsonify({"detail": "Conversation not found"}), 404

        rows = (
            db.query(models.Message)
            .filter(models.Message.conversation_id == conv_id)
            .order_by(models.Message.created_at.asc())
            .all()
        )
        results = []
        for m in rows:
            sender = db.query(models.User).filter(models.User.id == m.sender_id).first()
            results.append({
                "id": m.id,
                "conversation_id": m.conversation_id,
                "sender_username": sender.username if sender else "",
                "content": m.content,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            })
        return jsonify({"messages": results})
    finally:
        db.close()


@messages_bp.post("/<int:conv_id>/messages")
@require_auth
def send_message(conv_id):
    data = request.get_json(force=True) or {}
    content = (data.get("content") or "").strip()
    if not content:
        return jsonify({"detail": "Message cannot be empty"}), 422

    db = SessionLocal()
    try:
        conv = db.query(models.Conversation).filter(models.Conversation.id == conv_id).first()
        if not conv or g.current_user.id not in (conv.user_a_id, conv.user_b_id):
            return jsonify({"detail": "Conversation not found"}), 404

        msg = models.Message(conversation_id=conv_id, sender_id=g.current_user.id, content=content)
        db.add(msg)

        recipient_id = other_user_id(conv, g.current_user.id)
        notif = models.Notification(
            user_id=recipient_id,
            type="reply",
            title="New message",
            body=f"{g.current_user.full_name}: \"{content[:80]}\"",
            link=f"/inbox/{conv_id}",
        )
        db.add(notif)

        db.commit()
        db.refresh(msg)
        return jsonify({
            "success": True,
            "message": {
                "id": msg.id,
                "conversation_id": msg.conversation_id,
                "sender_username": g.current_user.username,
                "content": msg.content,
                "created_at": msg.created_at.isoformat() if msg.created_at else None,
            },
        })
    finally:
        db.close()
