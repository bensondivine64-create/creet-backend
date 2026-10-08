import threading
import time
from datetime import datetime, timedelta

from database import SessionLocal
import models

CHECK_INTERVAL_SECONDS = 600
STALE_LISTING_DAYS = 90


def expire_requests(db):
    n = (
        db.query(models.Listing)
        .filter(
            models.Listing.kind == "request",
            models.Listing.status == "active",
            models.Listing.deadline.isnot(None),
            models.Listing.deadline < datetime.utcnow(),
        )
        .update({"status": "expired"}, synchronize_session=False)
    )
    db.commit()
    return n


def expire_stale_listings(db):
    cutoff = datetime.utcnow() - timedelta(days=STALE_LISTING_DAYS)
    n = (
        db.query(models.Listing)
        .filter(
            models.Listing.kind.in_(["gig", "product"]),
            models.Listing.status == "active",
            models.Listing.created_at < cutoff,
            models.Listing.sold_at.is_(None),
        )
        .update({"status": "expired"}, synchronize_session=False)
    )
    db.commit()
    return n


def downgrade_expired_premium(db):
    n = (
        db.query(models.User)
        .filter(
            models.User.is_premium.is_(True),
            models.User.premium_expires.isnot(None),
            models.User.premium_expires < datetime.utcnow(),
        )
        .update({"is_premium": False}, synchronize_session=False)
    )
    db.commit()
    return n


def _run_loop():
    while True:
        try:
            db = SessionLocal()
            try:
                n1 = expire_requests(db)
                n2 = expire_stale_listings(db)
                n3 = downgrade_expired_premium(db)
                if n1 or n2 or n3:
                    print(f"[JOBS] expired_requests={n1} expired_listings={n2} premium_downgraded={n3}")
            finally:
                db.close()
        except Exception as e:
            print(f"[JOBS LOOP ERROR] {e}")
        time.sleep(CHECK_INTERVAL_SECONDS)


def start_job_scheduler():
    threading.Thread(target=_run_loop, daemon=True).start()
