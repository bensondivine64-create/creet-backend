import re
import requests
from datetime import datetime
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


AI_ENDPOINT = "https://curiousapis.name.ng/ai_gpt5"

SYSTEM_INSTRUCTIONS = """You are CREET's admin assistant. The admin will give you a command in plain English.
Respond with EXACTLY one line first, in this format, then nothing else on that line:
ACTION:<NONE|SUSPEND_USER|ACTIVATE_USER|VERIFY_USER|DELETE_LISTING|RESOLVE_REPORT>:<numeric_id_or_0>

Use NONE:0 if the command doesn't match a real action or is missing a clear numeric ID.
After that line, you may add a short plain-English explanation on the next line.

Admin command: """


def _execute_ai_action(db, action, target_id):
    if action == "SUSPEND_USER":
        user = db.query(models.User).filter(models.User.id == target_id).first()
        if not user:
            return False, "User not found"
        user.account_status = "suspended"
        db.commit()
        return True, None
    if action == "ACTIVATE_USER":
        user = db.query(models.User).filter(models.User.id == target_id).first()
        if not user:
            return False, "User not found"
        user.account_status = "active"
        db.commit()
        return True, None
    if action == "VERIFY_USER":
        user = db.query(models.User).filter(models.User.id == target_id).first()
        if not user:
            return False, "User not found"
        user.is_verified = True
        db.commit()
        return True, None
    if action == "DELETE_LISTING":
        listing = db.query(models.Listing).filter(models.Listing.id == target_id).first()
        if not listing:
            return False, "Listing not found"
        db.delete(listing)
        db.commit()
        return True, None
    if action == "RESOLVE_REPORT":
        report = db.query(models.Report).filter(models.Report.id == target_id).first()
        if not report:
            return False, "Report not found"
        report.status = "resolved"
        report.resolved_at = datetime.utcnow()
        db.commit()
        return True, None
    return False, None


@admin_bp.post("/ai-assistant")
@require_auth
@require_admin
def ai_assistant():
    db = g.db
    data = request.get_json(force=True) or {}
    command = (data.get("message") or "").strip()
    if not command:
        return jsonify({"detail": "Message is required"}), 422

    prompt = SYSTEM_INSTRUCTIONS + command

    try:
        resp = requests.get(AI_ENDPOINT, params={"query": prompt}, timeout=20)
        resp.raise_for_status()
        ai_json = resp.json()
        ai_text = ai_json.get("data", "")
    except Exception as e:
        log = models.AdminAiLog(
            admin_id=g.current_user.id, command=command, ai_raw_response=None,
            success=False, error=f"AI request failed: {e}",
        )
        db.add(log)
        db.commit()
        return jsonify({"reply": "Sorry, I couldn't reach the AI service right now.", "action_taken": None}), 502

    first_line = ai_text.strip().split("\n")[0].strip()
    match = re.match(r"ACTION:([A-Z_]+):(\d+)", first_line)

    action_taken = None
    success = False
    error = None

    if match:
        action, target_id_str = match.group(1), match.group(2)
        target_id = int(target_id_str)
        if action != "NONE":
            success, error = _execute_ai_action(db, action, target_id)
            action_taken = action if success else None

    reply_text = ai_text.strip()
    if match:
        reply_text = ai_text.strip()[len(first_line):].strip() or "Done."

    log = models.AdminAiLog(
        admin_id=g.current_user.id,
        command=command,
        ai_raw_response=ai_text,
        action_taken=action_taken,
        target_id=int(match.group(2)) if match else None,
        success=success,
        error=error,
    )
    db.add(log)
    db.commit()

    return jsonify({"reply": reply_text, "action_taken": action_taken, "error": error})


@admin_bp.get("/ai-assistant/logs")
@require_auth
@require_admin
def get_ai_logs():
    db = g.db
    rows = db.query(models.AdminAiLog).order_by(models.AdminAiLog.created_at.desc()).limit(50).all()
    return jsonify({
        "logs": [
            {
                "id": r.id,
                "command": r.command,
                "action_taken": r.action_taken,
                "target_id": r.target_id,
                "success": r.success,
                "error": r.error,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]
    })
