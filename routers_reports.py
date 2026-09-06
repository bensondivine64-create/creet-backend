from datetime import datetime
from flask import Blueprint, request, jsonify, g

import models
from auth import require_auth, require_admin

reports_bp = Blueprint("reports", __name__, url_prefix="/api/reports")

VALID_TARGET_TYPES = {"listing", "user"}


@reports_bp.post("")
@require_auth
def create_report():
    db = g.db
    data = request.get_json(force=True) or {}

    target_type = data.get("target_type", "")
    target_id = data.get("target_id")
    reason = (data.get("reason") or "").strip()
    description = (data.get("description") or "").strip()

    if target_type not in VALID_TARGET_TYPES:
        return jsonify({"detail": "Invalid target type"}), 422
    if not target_id or not reason:
        return jsonify({"detail": "Target and reason are required"}), 422

    report = models.Report(
        reporter_id=g.current_user.id,
        target_type=target_type,
        target_id=int(target_id),
        reason=reason[:100],
        description=description or None,
    )
    db.add(report)
    db.commit()
    return jsonify({"success": True, "id": report.id})


@reports_bp.get("/admin")
@require_auth
@require_admin
def list_reports_admin():
    db = g.db
    status = request.args.get("status", "").strip()
    limit = min(int(request.args.get("limit", 50)), 200)
    offset = int(request.args.get("offset", 0))

    query = db.query(models.Report)
    if status:
        query = query.filter(models.Report.status == status)

    total = query.count()
    rows = query.order_by(models.Report.created_at.desc()).offset(offset).limit(limit).all()

    results = []
    for r in rows:
        reporter = db.query(models.User).filter(models.User.id == r.reporter_id).first()

        target_label = None
        if r.target_type == "user":
            target_user = db.query(models.User).filter(models.User.id == r.target_id).first()
            target_label = target_user.full_name if target_user else "Deleted user"
        elif r.target_type == "listing":
            listing = db.query(models.Listing).filter(models.Listing.id == r.target_id).first()
            target_label = listing.title if listing else "Deleted listing"

        results.append({
            "id": r.id,
            "reporter": reporter.full_name if reporter else "Unknown",
            "reporter_username": reporter.username if reporter else None,
            "target_type": r.target_type,
            "target_id": r.target_id,
            "target_label": target_label,
            "reason": r.reason,
            "description": r.description,
            "status": r.status,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "resolved_at": r.resolved_at.isoformat() if r.resolved_at else None,
        })

    return jsonify({"reports": results, "total": total})


@reports_bp.post("/admin/<int:report_id>/resolve")
@require_auth
@require_admin
def resolve_report(report_id):
    db = g.db
    report = db.query(models.Report).filter(models.Report.id == report_id).first()
    if not report:
        return jsonify({"detail": "Report not found"}), 404
    report.status = "resolved"
    report.resolved_at = datetime.utcnow()
    db.commit()
    return jsonify({"success": True})
