from flask import Blueprint, request, jsonify, g

import models
from database import SessionLocal
from auth import require_auth
from serializers import is_badge_verified
from routers_blocks import is_blocked_either_way

network_bp = Blueprint("network", __name__, url_prefix="/api")


def _post_to_dict(post, author):
    return {
        "id": post.id,
        "content": post.content,
        "image_url": post.image_url,
        "created_at": post.created_at.isoformat() if post.created_at else None,
        "author": {
            "username": author.username,
            "full_name": author.full_name,
            "avatar": author.avatar,
            "role": author.role,
            "verified": is_badge_verified(author),
        },
    }


@network_bp.post("/follow/<int:user_id>")
@require_auth
def follow_user(user_id):
    db = g.db
    me = g.current_user

    if user_id == me.id:
        return jsonify({"detail": "You can't follow yourself"}), 400

    target = db.query(models.User).filter(models.User.id == user_id).first()
    if not target:
        return jsonify({"detail": "User not found"}), 404

    if not is_badge_verified(target):
        return jsonify({"detail": "Only verified accounts can be followed"}), 403

    if is_blocked_either_way(db, me.id, user_id):
        return jsonify({"detail": "You can't follow this user"}), 403

    existing = (
        db.query(models.Follow)
        .filter(models.Follow.follower_id == me.id, models.Follow.followed_id == user_id)
        .first()
    )
    if existing:
        return jsonify({"success": True, "following": True})

    follow = models.Follow(follower_id=me.id, followed_id=user_id)
    db.add(follow)
    db.commit()
    return jsonify({"success": True, "following": True})


@network_bp.delete("/follow/<int:user_id>")
@require_auth
def unfollow_user(user_id):
    db = g.db
    me = g.current_user

    db.query(models.Follow).filter(
        models.Follow.follower_id == me.id, models.Follow.followed_id == user_id
    ).delete(synchronize_session=False)
    db.commit()
    return jsonify({"success": True, "following": False})


@network_bp.get("/follow/status/<int:user_id>")
@require_auth
def follow_status(user_id):
    db = g.db
    me = g.current_user

    following = (
        db.query(models.Follow)
        .filter(models.Follow.follower_id == me.id, models.Follow.followed_id == user_id)
        .first()
        is not None
    )
    follower_count = db.query(models.Follow).filter(models.Follow.followed_id == user_id).count()
    following_count = db.query(models.Follow).filter(models.Follow.follower_id == user_id).count()

    return jsonify({
        "following": following,
        "follower_count": follower_count,
        "following_count": following_count,
    })


@network_bp.post("/posts")
@require_auth
def create_post():
    db = g.db
    me = g.current_user
    data = request.get_json(force=True) or {}

    content = (data.get("content") or "").strip()
    if not content:
        return jsonify({"detail": "Post can't be empty"}), 422
    if len(content) > 2000:
        return jsonify({"detail": "Post is too long"}), 422

    image_url = data.get("image_url") or None

    post = models.Post(author_id=me.id, content=content, image_url=image_url)
    db.add(post)
    db.commit()
    db.refresh(post)

    return jsonify({"success": True, "post": _post_to_dict(post, me)})


@network_bp.delete("/posts/<int:post_id>")
@require_auth
def delete_post(post_id):
    db = g.db
    me = g.current_user

    post = db.query(models.Post).filter(models.Post.id == post_id).first()
    if not post:
        return jsonify({"detail": "Post not found"}), 404
    if post.author_id != me.id:
        return jsonify({"detail": "You don't own this post"}), 403

    db.delete(post)
    db.commit()
    return jsonify({"success": True})


@network_bp.get("/posts/feed")
@require_auth
def get_network_feed():
    db = g.db
    me = g.current_user
    limit = min(int(request.args.get("limit", 20)), 50)
    offset = int(request.args.get("offset", 0))

    followed_ids = [
        row.followed_id
        for row in db.query(models.Follow.followed_id).filter(models.Follow.follower_id == me.id).all()
    ]
    author_ids = followed_ids + [me.id]

    base_query = db.query(models.Post).filter(models.Post.author_id.in_(author_ids))
    total = base_query.count()
    rows = base_query.order_by(models.Post.created_at.desc()).offset(offset).limit(limit).all()

    results = []
    for post in rows:
        author = db.query(models.User).filter(models.User.id == post.author_id).first()
        if author:
            results.append(_post_to_dict(post, author))

    return jsonify({"posts": results, "total": total})


@network_bp.get("/who-to-follow")
@require_auth
def who_to_follow():
    db = g.db
    me = g.current_user
    limit = min(int(request.args.get("limit", 10)), 30)

    already_following = {
        row.followed_id
        for row in db.query(models.Follow.followed_id).filter(models.Follow.follower_id == me.id).all()
    }
    exclude_ids = already_following | {me.id}

    candidates = (
        db.query(models.User)
        .filter(
            models.User.id.notin_(exclude_ids) if exclude_ids else True,
            (models.User.is_verified == True) | (models.User.is_admin == True) | (models.User.is_premium == True),  # noqa: E712
        )
        .order_by(models.User.created_at.desc())
        .limit(limit)
        .all()
    )

    results = []
    for u in candidates:
        if not is_badge_verified(u):
            continue
        results.append({
            "id": u.id,
            "username": u.username,
            "full_name": u.full_name,
            "avatar": u.avatar,
            "role": u.role,
            "short_bio": u.short_bio,
            "verified": True,
        })

    return jsonify({"users": results})


@network_bp.get("/posts/user/<string:username>")
def get_user_posts(username):
    db = SessionLocal()
    try:
        author = db.query(models.User).filter(models.User.username == username).first()
        if not author:
            return jsonify({"detail": "User not found"}), 404

        rows = (
            db.query(models.Post)
            .filter(models.Post.author_id == author.id)
            .order_by(models.Post.created_at.desc())
            .limit(50)
            .all()
        )
        return jsonify({"posts": [_post_to_dict(p, author) for p in rows]})
    finally:
        db.close()
