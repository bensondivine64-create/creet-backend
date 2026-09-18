from datetime import datetime
from currency import convert_currency

def is_badge_verified(user):
    if user.is_admin:
        return True
    if user.is_premium:
        if user.premium_expires and user.premium_expires < datetime.utcnow():
            pass
        else:
            return True
    if user.is_verified:
        return True
    return False

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
        "verified_badge": is_badge_verified(user),
        "avatar": user.avatar,
        "cover_photo": user.cover_photo,
        "bio": user.bio,
        "short_bio": user.short_bio,
        "location": user.location,
        "country": user.country,
        "phone_number": user.phone_number,
        "referral_source": user.referral_source,
        "date_of_birth": user.date_of_birth.isoformat() if user.date_of_birth else None,
        "categories": user.categories or [],
        "profile_completed": bool(user.profile_completed),
        "account_status": user.account_status or "active",
        "notify_messages": bool(user.notify_messages) if user.notify_messages is not None else True,
        "notify_announcements": bool(user.notify_announcements) if user.notify_announcements is not None else True,
        "notify_listing_activity": bool(user.notify_listing_activity) if user.notify_listing_activity is not None else True,
        "onboarding_extra": user.onboarding_extra or {},
        "hide_online_status": bool(user.hide_online_status) if user.hide_online_status is not None else False,
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }


ONLINE_THRESHOLD_SECONDS = 180


def presence_for(user):
    if user.hide_online_status or not user.last_active:
        return {"last_active": None, "is_online": False}
    online = (datetime.utcnow() - user.last_active).total_seconds() < ONLINE_THRESHOLD_SECONDS
    return {"last_active": user.last_active.isoformat(), "is_online": online}


def listing_to_dict(listing, seller, viewer_country=None):
    price = float(listing.price or 0)
    currency = listing.currency or "NGN"
    display_price = price
    display_currency = currency

    seller_country = getattr(seller, "country", None)
    if viewer_country and seller_country and viewer_country != seller_country:
        converted = convert_currency(price, currency, "USD")
        if converted is not None:
            display_price = converted
            display_currency = "USD"

    d = {
        "id": listing.id,
        "kind": listing.kind,
        "title": listing.title,
        "description": listing.description,
        "category": listing.category,
        "price": price,
        "currency": currency,
        "display_price": display_price,
        "display_currency": display_currency,
        "images": listing.images or [],
        "seller": {
            "username": seller.username,
            "full_name": seller.full_name,
            "avatar": seller.avatar,
            "verified": is_badge_verified(seller),
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
        d["sold_at"] = listing.sold_at.isoformat() if listing.sold_at else None
    elif listing.kind == "request":
        d["deadline"] = listing.deadline.isoformat() if listing.deadline else None
    return d


def comment_to_dict(comment, author):
    return {
        "id": comment.id,
        "listing_id": comment.listing_id,
        "author": {
            "username": author.username,
            "full_name": author.full_name,
            "avatar": author.avatar,
            "verified": is_badge_verified(author),
        },
        "content": comment.content,
        "created_at": comment.created_at.isoformat() if comment.created_at else None,
    }


def notification_to_dict(n, actor=None):
    return {
        "id": n.id,
        "type": n.type,
        "title": n.title,
        "body": n.body,
        "read": bool(n.is_read),
        "link": n.link,
        "created_at": n.created_at.isoformat() if n.created_at else None,
        "actor": {
            "username": actor.username,
            "full_name": actor.full_name,
            "avatar": actor.avatar,
        } if actor else None,
    }
