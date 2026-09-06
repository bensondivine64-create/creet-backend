from flask import Blueprint, jsonify, g, request
from serializers import user_to_dict, listing_to_dict

import models
from auth import require_auth, require_admin

admin_bp = Blueprint("admin", __name__, url_prefix="/api/admin")


@admin_bp.get("/stats")
@require_auth
@require_admin
def get_stats():
    db = g.db

    total_users = db.query(models.User).count()
    active_users = db.query(models.User).filter(models.User.account_status == "active").count()
    suspended_users = db.query(models.User).filter(models.User.account_status == "suspended").count()
    total_listings = db.query(models.Listing).count()
    total_reports = db.query(models.Report).count()
    pending_reports = db.query(models.Report).filter(models.Report.status == "pending").count()

    recent_users = (
        db.query(models.User)
        .order_by(models.User.created_at.desc())
        .limit(5)
        .all()
    )
    recent_listings = (
        db.query(models.Listing)
        .order_by(models.Listing.created_at.desc())
        .limit(5)
        .all()
    )

    activity = []
    for u in recent_users:
        activity.append({
            "type": "signup",
            "text": f"{u.full_name} joined as {u.role}",
            "created_at": u.created_at.isoformat() if u.created_at else None,
        })
    for l in recent_listings:
        activity.append({
            "type": "listing",
            "text": f"New {l.kind} posted: {l.title}",
            "created_at": l.created_at.isoformat() if l.created_at else None,
        })
    activity.sort(key=lambda a: a["created_at"] or "", reverse=True)
    activity = activity[:10]

    return jsonify({
        "total_users": total_users,
        "active_users": active_users,
        "suspended_users": suspended_users,
        "total_listings": total_listings,
        "total_reports": total_reports,
        "pending_reports": pending_reports,
        "recent_activity": activity,
    })


@admin_bp.get("/users")
@require_auth
@require_admin
def list_users():
    db = g.db
    search = request.args.get("search", "").strip()
    role = request.args.get("role", "").strip()
    status = request.args.get("status", "").strip()
    limit = min(int(request.args.get("limit", 50)), 200)
    offset = int(request.args.get("offset", 0))

    query = db.query(models.User)
    if search:
        like = f"%{search}%"
        query = query.filter(
            (models.User.full_name.ilike(like))
            | (models.User.username.ilike(like))
            | (models.User.email.ilike(like))
        )
    if role:
        query = query.filter(models.User.role == role)
    if status:
        query = query.filter(models.User.account_status == status)

    total = query.count()
    rows = query.order_by(models.User.created_at.desc()).offset(offset).limit(limit).all()

    return jsonify({
        "users": [user_to_dict(u) for u in rows],
        "total": total,
    })


@admin_bp.get("/users/<int:user_id>")
@require_auth
@require_admin
def get_user_detail(user_id):
    db = g.db
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        return jsonify({"detail": "User not found"}), 404

    listing_count = db.query(models.Listing).filter(models.Listing.seller_id == user_id).count()
    report_count = db.query(models.Report).filter(
        models.Report.target_type == "user", models.Report.target_id == user_id
    ).count()

    data = user_to_dict(user)
    data["listing_count"] = listing_count
    data["report_count"] = report_count
    return jsonify(data)


def _toggle_field(user_id, field, value):
    db = g.db
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        return jsonify({"detail": "User not found"}), 404
    setattr(user, field, value)
    db.commit()
    return jsonify(user_to_dict(user))


@admin_bp.post("/users/<int:user_id>/verify")
@require_auth
@require_admin
def verify_user(user_id):
    return _toggle_field(user_id, "is_verified", True)


@admin_bp.post("/users/<int:user_id>/unverify")
@require_auth
@require_admin
def unverify_user(user_id):
    return _toggle_field(user_id, "is_verified", False)


@admin_bp.post("/users/<int:user_id>/suspend")
@require_auth
@require_admin
def suspend_user(user_id):
    if user_id == g.current_user.id:
        return jsonify({"detail": "You can't suspend your own account"}), 400
    return _toggle_field(user_id, "account_status", "suspended")


@admin_bp.post("/users/<int:user_id>/activate")
@require_auth
@require_admin
def activate_user(user_id):
    return _toggle_field(user_id, "account_status", "active")


@admin_bp.post("/users/<int:user_id>/make-admin")
@require_auth
@require_admin
def make_admin(user_id):
    return _toggle_field(user_id, "is_admin", True)


@admin_bp.post("/users/<int:user_id>/remove-admin")
@require_auth
@require_admin
def remove_admin(user_id):
    if user_id == g.current_user.id:
        return jsonify({"detail": "You can't remove your own admin status"}), 400
    return _toggle_field(user_id, "is_admin", False)


@admin_bp.get("/listings")
@require_auth
@require_admin
def list_listings_admin():
    db = g.db
    search = request.args.get("search", "").strip()
    kind = request.args.get("kind", "").strip()
    limit = min(int(request.args.get("limit", 50)), 200)
    offset = int(request.args.get("offset", 0))

    query = db.query(models.Listing)
    if search:
        query = query.filter(models.Listing.title.ilike(f"%{search}%"))
    if kind:
        query = query.filter(models.Listing.kind == kind)

    total = query.count()
    rows = query.order_by(models.Listing.created_at.desc()).offset(offset).limit(limit).all()

    results = []
    for row in rows:
        seller = db.query(models.User).filter(models.User.id == row.seller_id).first()
        if seller:
            results.append(listing_to_dict(row, seller))

    return jsonify({"listings": results, "total": total})


@admin_bp.delete("/listings/<int:listing_id>")
@require_auth
@require_admin
def delete_listing_admin(listing_id):
    db = g.db
    listing = db.query(models.Listing).filter(models.Listing.id == listing_id).first()
    if not listing:
        return jsonify({"detail": "Listing not found"}), 404
    db.delete(listing)
    db.commit()
    return jsonify({"success": True})
