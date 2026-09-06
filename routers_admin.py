from flask import Blueprint, jsonify, g

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
