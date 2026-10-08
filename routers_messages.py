from datetime import datetime
from flask import Blueprint, request, jsonify, g

import models
from sqlalchemy import func, or_, case
from serializers import is_badge_verified, presence_for
from database import SessionLocal
from auth import require_auth
from routers_blocks import is_blocked_either_way
from cloud_storage import upload_image

messages_bp = Blueprint("messages", __name__, url_prefix="/api/conversations")

ALLOWED_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}


def _allowed_image(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_IMAGE_EXTENSIONS


def other_user_id(conv, my_id):
    return conv.user_b_id if conv.user_a_id == my_id else conv.user_a_id


def my_last_read(conv, my_id):
    return conv.user_a_last_read if conv.user_a_id == my_id else conv.user_b_last_read


def set_my_last_read(conv, my_id, when):
    if conv.user_a_id == my_id:
        conv.user_a_last_read = when
    else:
        conv.user_b_last_read = when


@messages_bp.get("")
@require_auth
def get_conversations():
    limit = min(int(request.args.get("limit", 30)), 50)
    offset = int(request.args.get("offset", 0))
    db = g.db
    me = g.current_user.id

    base_query = db.query(models.Conversation).filter(
        or_(models.Conversation.user_a_id == me, models.Conversation.user_b_id == me)
    )
    total = base_query.count()
    rows = (
        base_query.order_by(models.Conversation.created_at.desc())
        .offset(offset).limit(limit).all()
    )
    if not rows:
        return jsonify({"conversations": [], "total": total})

    conv_ids = [c.id for c in rows]
    other_ids = {other_user_id(c, me) for c in rows}
    listing_ids = {c.listing_id for c in rows if c.listing_id}

    others = {u.id: u for u in db.query(models.User).filter(models.User.id.in_(other_ids)).all()}

    last_ids = [
        r[0] for r in db.query(func.max(models.Message.id))
        .filter(models.Message.conversation_id.in_(conv_ids))
        .group_by(models.Message.conversation_id).all()
    ]
    last_msgs = {}
    if last_ids:
        for m in db.query(models.Message).filter(models.Message.id.in_(last_ids)).all():
            last_msgs[m.conversation_id] = m

    titles = {}
    if listing_ids:
        titles = {
            lid: t for lid, t in db.query(models.Listing.id, models.Listing.title)
            .filter(models.Listing.id.in_(listing_ids)).all()
        }

    last_read_col = case(
        (models.Conversation.user_a_id == me, models.Conversation.user_a_last_read),
        else_=models.Conversation.user_b_last_read,
    )
    unread_rows = (
        db.query(models.Message.conversation_id, func.count(models.Message.id))
        .join(models.Conversation, models.Conversation.id == models.Message.conversation_id)
        .filter(
            models.Message.conversation_id.in_(conv_ids),
            models.Message.sender_id != me,
            or_(last_read_col.is_(None), models.Message.created_at > last_read_col),
        )
        .group_by(models.Message.conversation_id).all()
    )
    unread = {cid: n for cid, n in unread_rows}

    results = []
    for conv in rows:
        other = others.get(other_user_id(conv, me))
        if not other:
            continue
        last_msg = last_msgs.get(conv.id)
        preview = last_msg.content if (last_msg and last_msg.content) else (
            "📷 Photo" if (last_msg and last_msg.image_url) else ""
        )
        if last_msg and last_msg.created_at:
            last_at = last_msg.created_at.isoformat()
        else:
            last_at = conv.created_at.isoformat() if conv.created_at else None
        results.append({
            "id": conv.id,
            "participant": {
                "username": other.username,
                "full_name": other.full_name,
                "avatar": other.avatar,
                "verified": is_badge_verified(other),
                **presence_for(other),
            },
            "listing_id": conv.listing_id,
            "listing_title": titles.get(conv.listing_id),
            "last_message": preview,
            "last_message_at": last_at,
            "unread_count": unread.get(conv.id, 0),
        })
    results.sort(key=lambda r: r["last_message_at"] or "", reverse=True)
    return jsonify({"conversations": results, "total": total})


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
        if is_blocked_either_way(db, me, seller_id):
            return jsonify({"detail": "You can't message this user"}), 403

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

        # Messaging about a listing is a stronger interest signal than just viewing it.
        buyer = db.query(models.User).filter(models.User.id == me).first()
        if buyer and listing.category:
            weights = dict(buyer.interest_weights or {})
            weights[listing.category] = weights.get(listing.category, 0) + 3
            buyer.interest_weights = weights

        db.commit()
        db.refresh(conv)
        return jsonify({"conversation_id": conv.id})
    finally:
        db.close()


@messages_bp.get("/<int:conv_id>/messages")
@require_auth
def get_messages(conv_id):
    db = g.db
    my_id = g.current_user.id
    conv = db.query(models.Conversation).filter(models.Conversation.id == conv_id).first()
    if not conv or my_id not in (conv.user_a_id, conv.user_b_id):
        return jsonify({"detail": "Conversation not found"}), 404

    set_my_last_read(conv, my_id, datetime.utcnow())
    db.commit()

    users = {
        u.id: u for u in db.query(models.User)
        .filter(models.User.id.in_([conv.user_a_id, conv.user_b_id])).all()
    }
    other = users.get(other_user_id(conv, my_id))

    limit = min(int(request.args.get("limit", 200)), 500)
    rows = (
        db.query(models.Message)
        .filter(models.Message.conversation_id == conv_id)
        .order_by(models.Message.id.desc()).limit(limit).all()
    )
    rows.reverse()
    results = [{
        "id": m.id,
        "conversation_id": m.conversation_id,
        "sender_username": users[m.sender_id].username if m.sender_id in users else "",
        "content": m.content or "",
        "image_url": m.image_url,
        "created_at": m.created_at.isoformat() if m.created_at else None,
    } for m in rows]

    participant = None
    if other:
        participant = {
            "username": other.username,
            "full_name": other.full_name,
            "avatar": other.avatar,
            "verified": is_badge_verified(other),
            **presence_for(other),
        }
    return jsonify({"messages": results, "participant": participant})


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

        other_id = other_user_id(conv, g.current_user.id)
        if is_blocked_either_way(db, g.current_user.id, other_id):
            return jsonify({"detail": "You can't message this user"}), 403

        msg = models.Message(conversation_id=conv_id, sender_id=g.current_user.id, content=content)
        db.add(msg)

        notif = models.Notification(
            user_id=other_id,
            type="reply",
            title="New message",
            body=f"{g.current_user.full_name}: \"{content[:80]}\"",
            link=f"/inbox/{conv_id}",
            actor_id=g.current_user.id,
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
                "content": msg.content or "",
                "image_url": msg.image_url,
                "created_at": msg.created_at.isoformat() if msg.created_at else None,
            },
        })
    finally:
        db.close()


@messages_bp.post("/<int:conv_id>/messages/image")
@require_auth
def send_message_image(conv_id):
    f = request.files.get("image")
    if not f or not f.filename:
        return jsonify({"detail": "No image provided"}), 422
    if not _allowed_image(f.filename):
        return jsonify({"detail": "Allowed formats: jpg, jpeg, png, webp"}), 422

    db = SessionLocal()
    try:
        conv = db.query(models.Conversation).filter(models.Conversation.id == conv_id).first()
        if not conv or g.current_user.id not in (conv.user_a_id, conv.user_b_id):
            return jsonify({"detail": "Conversation not found"}), 404

        other_id = other_user_id(conv, g.current_user.id)
        if is_blocked_either_way(db, g.current_user.id, other_id):
            return jsonify({"detail": "You can't message this user"}), 403

        image_url = upload_image(f, folder="creet/messages")
        msg = models.Message(conversation_id=conv_id, sender_id=g.current_user.id, content="", image_url=image_url)
        db.add(msg)

        notif = models.Notification(
            user_id=other_id,
            type="reply",
            title="New message",
            body=f"{g.current_user.full_name} sent a photo",
            link=f"/inbox/{conv_id}",
            actor_id=g.current_user.id,
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
                "content": msg.content or "",
                "image_url": msg.image_url,
                "created_at": msg.created_at.isoformat() if msg.created_at else None,
            },
        })
    finally:
        db.close()
