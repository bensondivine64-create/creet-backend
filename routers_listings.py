from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify, g
from cloud_storage import upload_image

import models
from database import SessionLocal
from auth import require_auth
from serializers import listing_to_dict

listings_bp = Blueprint("listings", __name__, url_prefix="/api/listings")

ROLE_FOR_KIND = {"gig": "freelancer", "product": "vendor", "request": "buyer"}
EDITABLE_KINDS = {"product", "request"}


@listings_bp.get("")
def get_listings():
    kind = request.args.get("type", "gig")
    search = request.args.get("search", "")
    category = request.args.get("category", "")
    limit = int(request.args.get("limit", 40))
    offset = int(request.args.get("offset", 0))

    db = SessionLocal()
    try:
        cutoff = datetime.utcnow() - timedelta(days=6)
        query = db.query(models.Listing).filter(
            models.Listing.kind == kind, models.Listing.status == "active"
        )
        query = query.filter(
            (models.Listing.sold_at.is_(None)) | (models.Listing.sold_at > cutoff)
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


def _get_owned_listing(db, listing_id):
    listing = db.query(models.Listing).filter(models.Listing.id == listing_id).first()
    if not listing:
        return None, jsonify({"detail": "This listing doesn't exist"}), 404
    if listing.kind not in EDITABLE_KINDS:
        return None, jsonify({"detail": "This listing type can't be edited here"}), 403
    if listing.seller_id != g.current_user.id:
        return None, jsonify({"detail": "You don't own this listing"}), 403
    return listing, None, None


@listings_bp.put("/<int:listing_id>")
@require_auth
def update_listing(listing_id):
    db = g.db
    listing, err_resp, err_code = _get_owned_listing(db, listing_id)
    if listing is None:
        return err_resp, err_code

    data = request.get_json(force=True) or {}

    if "title" in data and data["title"]:
        listing.title = data["title"][:255]
    if "description" in data and data["description"]:
        listing.description = data["description"]
    if "category" in data and data["category"]:
        listing.category = data["category"]
    if "price" in data:
        listing.price = data.get("price", 0)
    if "images" in data and isinstance(data["images"], list):
        listing.images = [str(u) for u in data["images"] if isinstance(u, str)][:6]

    if listing.kind == "product":
        if "condition" in data:
            listing.condition_status = data["condition"]
        if "stock" in data:
            listing.stock = data.get("stock", 0)
    elif listing.kind == "request":
        if "deadline" in data:
            deadline_str = data.get("deadline")
            if deadline_str:
                try:
                    listing.deadline = datetime.fromisoformat(deadline_str)
                except ValueError:
                    pass
            else:
                listing.deadline = None

    db.commit()
    db.refresh(listing)
    return jsonify(listing_to_dict(listing, g.current_user))


@listings_bp.delete("/<int:listing_id>")
@require_auth
def delete_listing(listing_id):
    db = g.db
    listing, err_resp, err_code = _get_owned_listing(db, listing_id)
    if listing is None:
        return err_resp, err_code

    db.delete(listing)
    db.commit()
    return jsonify({"success": True})


@listings_bp.post("/<int:listing_id>/mark-sold")
@require_auth
def mark_sold(listing_id):
    db = g.db
    listing, err_resp, err_code = _get_owned_listing(db, listing_id)
    if listing is None:
        return err_resp, err_code
    if listing.kind != "product":
        return jsonify({"detail": "Only products can be marked as sold"}), 422

    listing.sold_at = datetime.utcnow()
    db.commit()
    db.refresh(listing)
    return jsonify(listing_to_dict(listing, g.current_user))


ALLOWED_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}


def _allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_IMAGE_EXTENSIONS


@listings_bp.post("/upload-images")
@require_auth
def upload_images():
    files = request.files.getlist("images")
    if not files:
        return jsonify({"detail": "No images provided"}), 422

    urls = []
    for f in files[:6]:
        if not f or not f.filename or not _allowed_file(f.filename):
            continue
        urls.append(upload_image(f, folder="creet/listings"))

    if not urls:
        return jsonify({"detail": "No valid images (allowed: jpg, jpeg, png, webp)"}), 422

    return jsonify({"urls": urls})
