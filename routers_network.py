from flask import Blueprint, request, jsonify, g

import models
from database import SessionLocal
from auth import require_auth
from serializers import is_badge_verified
from routers_blocks import is_blocked_either_way
from cloud_storage import upload_image

network_bp = Blueprint("network", __name__, url_prefix="/api")


def _post_to_dict(post, author, db=None, viewer_id=None):
    like_count = 0
    comment_count = 0
    liked_by_me = False
    if db is not None:
        like_count = db.query(models.PostLike).filter(models.PostLike.post_id == post.id).count()
        comment_count = db.query(models.PostComment).filter(models.PostComment.post_id == post.id).count()
        if viewer_id:
            liked_by_me = (
                db.query(models.PostLike)
                .filter(models.PostLike.post_id == post.id, models.PostLike.user_id == viewer_id)
                .first()
                is not None
            )
    return {
        "id": post.id,
        "content": post.content,
        "image_url": post.image_url,
        "created_at": post.created_at.isoformat() if post.created_at else None,
        "like_count": like_count,
        "comment_count": comment_count,
        "liked_by_me": liked_by_me,
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


ALLOWED_POST_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}


def _allowed_post_image(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_POST_IMAGE_EXTENSIONS


@network_bp.post("/posts/upload-image")
@require_auth
def upload_post_image():
    f = request.files.get("image")
    if not f or not f.filename:
        return jsonify({"detail": "No image provided"}), 422
    if not _allowed_post_image(f.filename):
        return jsonify({"detail": "Allowed formats: jpg, jpeg, png, webp"}), 422

    url = upload_image(f, folder="creet/posts")
    return jsonify({"url": url})


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

    return jsonify({"success": True, "post": _post_to_dict(post, me, db=db, viewer_id=me.id)})


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

    followed_ids = {
        row.followed_id
        for row in db.query(models.Follow.followed_id).filter(models.Follow.follower_id == me.id).all()
    }
    viewer_categories = set(me.categories or [])

    total = db.query(models.Post).count()
    candidates = (
        db.query(models.Post)
        .order_by(models.Post.created_at.desc())
        .limit(300)
        .all()
    )

    def score(post):
        author = db.query(models.User).filter(models.User.id == post.author_id).first()
        if not author:
            return (-1, post.created_at)
        is_followed = author.id in followed_ids
        category_match = bool(viewer_categories & set(author.categories or []))
        if is_followed and category_match:
            return (3, post.created_at)
        if is_followed:
            return (2, post.created_at)
        if category_match:
            return (1, post.created_at)
        return (0, post.created_at)

    scored = sorted(candidates, key=score, reverse=True)
    page = scored[offset:offset + limit]

    results = []
    for post in page:
        author = db.query(models.User).filter(models.User.id == post.author_id).first()
        if author:
            results.append(_post_to_dict(post, author, db=db, viewer_id=me.id))

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


@network_bp.post("/posts/<int:post_id>/like")
@require_auth
def like_post(post_id):
    db = g.db
    me = g.current_user

    post = db.query(models.Post).filter(models.Post.id == post_id).first()
    if not post:
        return jsonify({"detail": "Post not found"}), 404

    existing = (
        db.query(models.PostLike)
        .filter(models.PostLike.post_id == post_id, models.PostLike.user_id == me.id)
        .first()
    )
    if not existing:
        db.add(models.PostLike(post_id=post_id, user_id=me.id))
        db.commit()

    like_count = db.query(models.PostLike).filter(models.PostLike.post_id == post_id).count()
    return jsonify({"success": True, "liked": True, "like_count": like_count})


@network_bp.delete("/posts/<int:post_id>/like")
@require_auth
def unlike_post(post_id):
    db = g.db
    me = g.current_user

    db.query(models.PostLike).filter(
        models.PostLike.post_id == post_id, models.PostLike.user_id == me.id
    ).delete(synchronize_session=False)
    db.commit()

    like_count = db.query(models.PostLike).filter(models.PostLike.post_id == post_id).count()
    return jsonify({"success": True, "liked": False, "like_count": like_count})


def _comment_to_dict(c, author):
    return {
        "id": c.id,
        "content": c.content,
        "created_at": c.created_at.isoformat() if c.created_at else None,
        "author": {
            "username": author.username,
            "full_name": author.full_name,
            "avatar": author.avatar,
            "verified": is_badge_verified(author),
        },
    }


@network_bp.get("/posts/<int:post_id>/comments")
def get_post_comments(post_id):
    db = SessionLocal()
    try:
        rows = (
            db.query(models.PostComment)
            .filter(models.PostComment.post_id == post_id)
            .order_by(models.PostComment.created_at.asc())
            .all()
        )
        results = []
        for c in rows:
            author = db.query(models.User).filter(models.User.id == c.author_id).first()
            if author:
                results.append(_comment_to_dict(c, author))
        return jsonify({"comments": results})
    finally:
        db.close()


@network_bp.post("/posts/<int:post_id>/comments")
@require_auth
def add_post_comment(post_id):
    db = g.db
    me = g.current_user

    post = db.query(models.Post).filter(models.Post.id == post_id).first()
    if not post:
        return jsonify({"detail": "Post not found"}), 404

    data = request.get_json(force=True) or {}
    content = (data.get("content") or "").strip()
    if not content:
        return jsonify({"detail": "Comment can't be empty"}), 422
    if len(content) > 1000:
        return jsonify({"detail": "Comment is too long"}), 422

    comment = models.PostComment(post_id=post_id, author_id=me.id, content=content)
    db.add(comment)
    db.commit()
    db.refresh(comment)

    return jsonify({"success": True, "comment": _comment_to_dict(comment, me)})


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
        return jsonify({"posts": [_post_to_dict(p, author, db=db) for p in rows]})
    finally:
        db.close()
