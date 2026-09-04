import os
import uuid
from datetime import datetime
from flask import Blueprint, request, jsonify, g

import models
from database import SessionLocal
from auth import require_auth
from serializers import listing_to_dict

listings_bp = Blueprint("listings", __name__, url_prefix="/api/listings")

ROLE_FOR_KIND = {"gig": "freelancer", "product": "vendor", "request": "buyer"}


@listings_bp.get("")
def get_listings():
    kind = request.args.get("type", "gig")
    search = request.args.get("search", "")
    category = request.args.get("category", "")
    limit = int(request.args.get("limit", 40))
    offset = int(request.args.get("offset", 0))

    db = SessionLocal()
    try:
        query = db.query(models.Listing).filter(
            models.Listing.kind == kind, models.Listing.status == "active"
        )
        if search:
            like = f"%{search}%"
            query = query.filter(models.Listing.title.ilike(like))
        if category:
            query = query.filter(models.Listing.category == category)

        total = query.count()
        rows = query.order_by(models.Listing.created_at.desc()).offset(offset).limit(limit).all()

        results = []
        for row in rows:
            seller = db.query(models.User).filter(models.User.id == row.seller_id).first()
            if seller:
                results.append(listing_to_dict(row, seller))

        return jsonify({"listings": results, "total": total})
    finally:
        db.close()


@listings_bp.get("/mine")
@require_auth
def get_my_listings():
    db = SessionLocal()
    try:
        rows = (
            db.query(models.Listing)
            .filter(models.Listing.seller_id == g.current_user.id)
            .order_by(models.Listing.created_at.desc())
            .all()
        )
        results = [listing_to_dict(row, g.current_user) for row in rows]
        return jsonify({"listings": results, "total": len(results)})
    finally:
        db.close()


@listings_bp.get("/<int:listing_id>")
def get_listing(listing_id):
    db = SessionLocal()
    try:
        row = db.query(models.Listing).filter(models.Listing.id == listing_id).first()
        if not row:
            return jsonify({"detail": "This listing doesn't exist"}), 404
        seller = db.query(models.User).filter(models.User.id == row.seller_id).first()
        if not seller:
            return jsonify({"detail": "This listing doesn't exist"}), 404
        return jsonify(listing_to_dict(row, seller))
    finally:
        db.close()


def _create_listing(kind, required_fields):
    db = SessionLocal()
    try:
        expected_role = ROLE_FOR_KIND[kind]
        if g.current_user.role != expected_role:
            return jsonify({"detail": f"Only {expected_role}s can post this"}), 403

        data = request.get_json(force=True) or {}
        for field in required_fields:
            if field not in data or data[field] in (None, ""):
                return jsonify({"detail": f"{field} is required"}), 422

        images = data.get("images", [])
        if not isinstance(images, list):
            images = []
        images = [str(u) for u in images if isinstance(u, str)][:6]

        listing = models.Listing(
            seller_id=g.current_user.id,
            kind=kind,
            title=data["title"],
            description=data["description"],
            category=data["category"],
            price=data.get("price", 0),
            currency="NGN",
            images=images,
        )
        if kind == "gig":
            listing.delivery_days = data.get("delivery_days", 1)
        elif kind == "product":
            listing.condition_status = data.get("condition", "new")
            listing.stock = data.get("stock", 0)
        elif kind == "request":
            deadline_str = data.get("deadline")
            if deadline_str:
                try:
                    listing.deadline = datetime.fromisoformat(deadline_str)
                except ValueError:
                    pass

        db.add(listing)
        db.commit()
        db.refresh(listing)
        return jsonify({"success": True, "id": listing.id})
    finally:
        db.close()


@listings_bp.post("/gigs")
@require_auth
def create_gig():
    return _create_listing("gig", ["title", "description", "category"])


@listings_bp.post("/products")
@require_auth
def create_product():
    return _create_listing("product", ["title", "description", "category"])


@listings_bp.post("/requests")
@require_auth
def create_request():
    return _create_listing("request", ["title", "description", "category"])


ALLOWED_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}
UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "static", "uploads", "listings")


def _allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_IMAGE_EXTENSIONS


@listings_bp.post("/upload-images")
@require_auth
def upload_images():
    files = request.files.getlist("images")
    if not files:
        return jsonify({"detail": "No images provided"}), 422

    os.makedirs(UPLOAD_DIR, exist_ok=True)
    urls = []
    for f in files[:6]:
        if not f or not f.filename or not _allowed_file(f.filename):
            continue
        ext = f.filename.rsplit(".", 1)[1].lower()
        unique_name = f"{uuid.uuid4().hex}.{ext}"
        f.save(os.path.join(UPLOAD_DIR, unique_name))
        urls.append(f"/static/uploads/listings/{unique_name}")

    if not urls:
        return jsonify({"detail": "No valid images (allowed: jpg, jpeg, png, webp)"}), 422

    return jsonify({"urls": urls})
