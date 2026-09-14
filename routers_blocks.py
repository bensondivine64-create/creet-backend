from flask import Blueprint, jsonify, g

import models
from auth import require_auth

blocks_bp = Blueprint("blocks", __name__, url_prefix="/api/blocks")


def is_blocked_either_way(db, user_a_id, user_b_id):
    return (
        db.query(models.Block)
        .filter(
            ((models.Block.blocker_id == user_a_id) & (models.Block.blocked_id == user_b_id))
            | ((models.Block.blocker_id == user_b_id) & (models.Block.blocked_id == user_a_id))
        )
        .first()
        is not None
    )


@blocks_bp.get("")
@require_auth
def list_blocked():
    db = g.db
    me = g.current_user.id
    rows = db.query(models.Block).filter(models.Block.blocker_id == me).all()
    results = []
    for b in rows:
        u = db.query(models.User).filter(models.User.id == b.blocked_id).first()
        if u:
            results.append({
                "id": u.id,
                "username": u.username,
                "full_name": u.full_name,
                "avatar": u.avatar,
            })
    return jsonify({"blocked": results})


@blocks_bp.post("/<int:user_id>")
@require_auth
def block_user(user_id):
    db = g.db
    me = g.current_user.id
    if user_id == me:
        return jsonify({"detail": "You can't block yourself"}), 400

    target = db.query(models.User).filter(models.User.id == user_id).first()
    if not target:
        return jsonify({"detail": "User not found"}), 404

    existing = (
        db.query(models.Block)
        .filter(models.Block.blocker_id == me, models.Block.blocked_id == user_id)
        .first()
    )
    if existing:
        return jsonify({"success": True})

    block = models.Block(blocker_id=me, blocked_id=user_id)
    db.add(block)
    db.commit()
    return jsonify({"success": True})


@blocks_bp.delete("/<int:user_id>")
@require_auth
def unblock_user(user_id):
    db = g.db
    me = g.current_user.id
    block = (
        db.query(models.Block)
        .filter(models.Block.blocker_id == me, models.Block.blocked_id == user_id)
        .first()
    )
    if block:
        db.delete(block)
        db.commit()
    return jsonify({"success": True})


@blocks_bp.get("/<int:user_id>/status")
@require_auth
def block_status(user_id):
    db = g.db
    me = g.current_user.id
    i_blocked_them = (
        db.query(models.Block)
        .filter(models.Block.blocker_id == me, models.Block.blocked_id == user_id)
        .first()
        is not None
    )
    they_blocked_me = (
        db.query(models.Block)
        .filter(models.Block.blocker_id == user_id, models.Block.blocked_id == me)
        .first()
        is not None
    )
    return jsonify({"i_blocked_them": i_blocked_them, "they_blocked_me": they_blocked_me})
