def user_to_dict(user):
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role,
        "is_admin": bool(user.is_admin),
        "is_verified": bool(user.is_verified),
        "is_premium": bool(user.is_premium),
        "avatar": user.avatar,
        "bio": user.bio,
        "location": user.location,
        "categories": user.categories or [],
        "profile_completed": bool(user.profile_completed),
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }


def listing_to_dict(listing, seller):
    d = {
        "id": listing.id,
        "kind": listing.kind,
        "title": listing.title,
        "description": listing.description,
        "category": listing.category,
        "price": float(listing.price or 0),
        "currency": listing.currency or "NGN",
        "images": listing.images or [],
        "seller": {
            "username": seller.username,
            "full_name": seller.full_name,
            "avatar": seller.avatar,
            "verified": bool(seller.is_verified),
        },
        "rating_avg": float(listing.rating_avg or 0),
        "rating_count": listing.rating_count or 0,
        "created_at": listing.created_at.isoformat() if listing.created_at else None,
    }
    if listing.kind == "gig":
        d["delivery_days"] = listing.delivery_days
    elif listing.kind == "product":
        d["condition"] = listing.condition_status
        d["stock"] = listing.stock
    elif listing.kind == "request":
        d["deadline"] = listing.deadline.isoformat() if listing.deadline else None
    return d
