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
SERIOUS_ACTIONS = {"SUSPEND_USER", "DELETE_LISTING", "MAKE_ADMIN", "SET_MAINTENANCE", "ANNOUNCE"}

SYSTEM_INSTRUCTIONS = """You are CREET's admin assistant, helping the admin manage the platform (users, listings, reports).

If the admin's message is casual conversation, a greeting, a question, or anything that isn't a specific instruction to take action \
(e.g. "hey", "hi", "how are you", "what can you do", "how many users do we have") \
just reply naturally and conversationally. Do NOT include any ACTION line for these.

Only when the admin is clearly asking you to perform a specific action, respond with EXACTLY one line \
FIRST, in this format, then your explanation on the next line:
ACTION:<SUSPEND_USER|ACTIVATE_USER|VERIFY_USER|UNVERIFY_USER|MAKE_ADMIN|REMOVE_ADMIN|DELETE_LISTING|RESOLVE_REPORT|SET_MAINTENANCE|ANNOUNCE>:<param>

For most actions, <param> is the numeric target ID.
For SET_MAINTENANCE, <param> is 1 to turn maintenance mode ON or 0 to turn it OFF.
For ANNOUNCE, <param> is 0=all users, 1=buyers only, 2=freelancers only, 3=vendors only \
— and you MUST add a second line: MESSAGE:<the announcement text, taken from what the admin asked to announce>

If they seem to want an action but didn't give enough info (e.g. no ID, no announcement text), just ask them for it in plain conversational text — don't use the ACTION line.

Admin message: """


def _execute_ai_action(db, action, target_id, message=None):
    if action == "SUSPEND_USER":
        user = db.query(models.User).filter(models.User.id == target_id).first()
        if not user:
            return False, "User not found"
        if user.is_admin:
            return False, "Can't suspend an admin"
        from datetime import datetime, timedelta
        user.account_status = "suspended"
        user.suspension_type = "serious"
        user.suspension_until = datetime.utcnow() + timedelta(days=30)
        user.suspension_reason = "Suspended by admin via AI assistant"
        user.suspension_count = (user.suspension_count or 0) + 1
        db.commit()
        return True, None
    if action == "ACTIVATE_USER":
        user = db.query(models.User).filter(models.User.id == target_id).first()
        if not user:
            return False, "User not found"
        user.account_status = "active"
        user.suspension_type = None
        user.suspension_until = None
        db.commit()
        return True, None
    if action == "VERIFY_USER":
        user = db.query(models.User).filter(models.User.id == target_id).first()
        if not user:
            return False, "User not found"
        user.is_verified = True
        db.commit()
        return True, None
    if action == "UNVERIFY_USER":
        user = db.query(models.User).filter(models.User.id == target_id).first()
        if not user:
            return False, "User not found"
        user.is_verified = False
        db.commit()
        return True, None
    if action == "MAKE_ADMIN":
        user = db.query(models.User).filter(models.User.id == target_id).first()
        if not user:
            return False, "User not found"
        user.is_admin = True
        db.commit()
        return True, None
    if action == "REMOVE_ADMIN":
        user = db.query(models.User).filter(models.User.id == target_id).first()
        if not user:
            return False, "User not found"
        if target_id == g.current_user.id:
            return False, "Can't remove your own admin status"
        user.is_admin = False
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
    if action == "SET_MAINTENANCE":
        from routers_settings import _get_settings
        settings = _get_settings(db)
        settings.maintenance_mode = bool(target_id)
        db.commit()
        return True, None
    if action == "ANNOUNCE":
        if not message:
            return False, "No announcement message provided"
        from routers_settings import _get_settings
        role_by_index = {0: None, 1: "buyer", 2: "freelancer", 3: "vendor"}
        role = role_by_index.get(target_id)
        query = db.query(models.User)
        if role:
            query = query.filter(models.User.role == role)
        for u in query.all():
            db.add(models.Notification(user_id=u.id, type="announcement", title="Announcement", body=message))
        settings = _get_settings(db)
        settings.banner_active = True
        settings.banner_text = message
        db.commit()
        return True, None
    return False, None


def _build_context_snapshot(db):
    total_users = db.query(models.User).count()
    active_users = db.query(models.User).filter(models.User.account_status == "active").count()
    suspended_users = db.query(models.User).filter(models.User.account_status == "suspended").count()
    total_listings = db.query(models.Listing).count()
    total_reports = db.query(models.Report).count()
    pending_reports = db.query(models.Report).filter(models.Report.status == "pending").count()

    from routers_settings import _get_settings
    settings = _get_settings(db)

    return (
        f"LIVE PLATFORM DATA (use these real numbers when answering questions, never guess):\n"
        f"- Total users: {total_users} (active: {active_users}, suspended: {suspended_users})\n"
        f"- Total listings: {total_listings}\n"
        f"- Total reports: {total_reports} (pending: {pending_reports})\n"
        f"- Maintenance mode: {'ON' if settings.maintenance_mode else 'OFF'}\n"
        f"- Announcement banner: {'active — ' + (settings.banner_text or '') if settings.banner_active else 'inactive'}\n"
    )


@admin_bp.post("/ai-assistant")
@require_auth
@require_admin
def ai_assistant():
    db = g.db
    data = request.get_json(force=True) or {}
    command = (data.get("message") or "").strip()
    history = data.get("history") or []
    if not command:
        return jsonify({"detail": "Message is required"}), 422

    context = _build_context_snapshot(db)

    convo = ""
    for h in history[-8:]:
        role_label = "Admin" if h.get("role") == "admin" else "You"
        convo += f"{role_label}: {h.get('text', '')}\n"

    prompt = SYSTEM_INSTRUCTIONS + context + "\nConversation so far:\n" + convo + f"Admin: {command}"

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

    lines = ai_text.strip().split("\n")
    first_line = lines[0].strip()
    match = re.match(r"ACTION:([A-Z_]+):(\d+)", first_line)

    action_taken = None
    success = False
    error = None
    pending_action = None
    announce_message = None

    reply_text = ai_text.strip()
    if match:
        reply_text = ai_text.strip()[len(first_line):].strip() or "Done."

    if match:
        action, target_id_str = match.group(1), match.group(2)
        target_id = int(target_id_str)

        if action == "ANNOUNCE":
            for line in lines[1:]:
                m2 = re.match(r"MESSAGE:(.*)", line.strip())
                if m2:
                    announce_message = m2.group(1).strip()
                    break

        if action != "NONE" and action in SERIOUS_ACTIONS:
            pending_action = {"action": action, "target_id": target_id, "message": announce_message}
            if action == "SET_MAINTENANCE":
                reply_text = f"This will turn maintenance mode {'ON' if target_id else 'OFF'}. Confirm to proceed."
            elif action == "ANNOUNCE":
                reply_text = f'This will announce: "{announce_message}". Confirm to proceed.'
            else:
                reply_text = f"This will {action.replace('_', ' ').lower()} (ID {target_id}). Confirm to proceed."
        elif action != "NONE":
            success, error = _execute_ai_action(db, action, target_id, announce_message)
            action_taken = action if success else None

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

    return jsonify({
        "reply": reply_text,
        "action_taken": action_taken,
        "error": error,
        "pending_action": pending_action,
    })


@admin_bp.post("/ai-assistant/confirm")
@require_auth
@require_admin
def confirm_ai_action():
    db = g.db
    data = request.get_json(force=True) or {}
    action = data.get("action", "")
    target_id = data.get("target_id")
    message = data.get("message")

    if action not in SERIOUS_ACTIONS or target_id is None:
        return jsonify({"detail": "Invalid confirmation request"}), 422

    success, error = _execute_ai_action(db, action, int(target_id), message)

    log = models.AdminAiLog(
        admin_id=g.current_user.id,
        command=f"[CONFIRMED] {action}:{target_id}",
        ai_raw_response=None,
        action_taken=action if success else None,
        target_id=int(target_id),
        success=success,
        error=error,
    )
    db.add(log)
    db.commit()

    return jsonify({"success": success, "error": error})


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
