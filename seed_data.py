"""One-off script to populate sample listings for design/UX testing.
Run once: python seed_data.py
"""
from database import SessionLocal
from auth import hash_password
import models

SAMPLE_USERS = [
    {"username": "aisha_designs", "email": "aisha.seed@example.com", "full_name": "Aisha Bello", "role": "freelancer", "is_verified": True},
    {"username": "chidi_dev", "email": "chidi.seed@example.com", "full_name": "Chidi Okafor", "role": "freelancer", "is_verified": True},
    {"username": "tundeelectronics", "email": "tunde.seed@example.com", "full_name": "Tunde Electronics", "role": "vendor", "is_verified": True},
    {"username": "lagosfashionhub", "email": "lagosfashion.seed@example.com", "full_name": "Lagos Fashion Hub", "role": "vendor", "is_verified": False},
]

SAMPLE_GIGS = [
    {"title": "I will design a modern logo for your brand", "description": "Professional logo design with unlimited revisions, delivered in all formats.", "category": "Design & Creative", "price": 15000, "delivery_days": 3},
    {"title": "I will build a responsive website with React", "description": "Full-stack website development using React and Node.js, mobile-first.", "category": "Web Development", "price": 80000, "delivery_days": 7},
    {"title": "I will write SEO-optimized blog content", "description": "Well-researched, engaging blog posts optimized for search rankings.", "category": "Writing & Translation", "price": 12000, "delivery_days": 2},
    {"title": "I will edit your wedding or event video", "description": "Professional video editing with color grading and music sync.", "category": "Video & Audio", "price": 25000, "delivery_days": 5},
]

SAMPLE_PRODUCTS = [
    {"title": "iPhone 13 Pro, 128GB - Excellent Condition", "description": "Barely used, comes with original box and charger.", "category": "Electronics", "price": 450000, "condition": "used", "stock": 1},
    {"title": "Wireless Bluetooth Headphones", "description": "Brand new noise-cancelling headphones, 30hr battery life.", "category": "Electronics", "price": 28000, "condition": "new", "stock": 15},
    {"title": "Ankara Print Dress - Custom Sizes", "description": "Handmade Ankara dresses, custom tailored to your size.", "category": "Fashion", "price": 18000, "condition": "new", "stock": 8},
]

SAMPLE_REQUESTS = [
    {"title": "I need a logo designer for my startup", "description": "Looking for a creative designer to build brand identity for a fintech startup.", "category": "Design & Creative", "price": 20000},
    {"title": "Need a mobile app developer", "description": "Building a delivery app, need someone experienced with React Native.", "category": "Web Development", "price": 150000},
]


def run():
    db = SessionLocal()
    try:
        created_users = {}
        for u in SAMPLE_USERS:
            existing = db.query(models.User).filter(models.User.email == u["email"]).first()
            if existing:
                created_users[u["role"]] = created_users.get(u["role"], []) + [existing]
                continue
            user = models.User(
                username=u["username"],
                email=u["email"],
                password_hash=hash_password("SeedPassword123!"),
                full_name=u["full_name"],
                role=u["role"],
                is_verified=u["is_verified"],
                profile_completed=True,
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            created_users[u["role"]] = created_users.get(u["role"], []) + [user]
            print(f"Created user: {user.username}")

        freelancers = created_users.get("freelancer", [])
        vendors = created_users.get("vendor", [])

        buyer = db.query(models.User).filter(models.User.role == "buyer").first()
        if not buyer:
            print("No buyer account found — requests will be skipped. Sign up a buyer account first if you want sample requests.")

        for i, gig in enumerate(SAMPLE_GIGS):
            seller = freelancers[i % len(freelancers)]
            exists = db.query(models.Listing).filter(models.Listing.title == gig["title"]).first()
            if exists:
                continue
            listing = models.Listing(
                seller_id=seller.id,
                kind="gig",
                title=gig["title"],
                description=gig["description"],
                category=gig["category"],
                price=gig["price"],
                currency="NGN",
                delivery_days=gig["delivery_days"],
                rating_avg=4.5 + (i % 5) * 0.1,
                rating_count=10 + i * 7,
            )
            db.add(listing)
            print(f"Created gig: {gig['title']}")

        for i, product in enumerate(SAMPLE_PRODUCTS):
            seller = vendors[i % len(vendors)]
            exists = db.query(models.Listing).filter(models.Listing.title == product["title"]).first()
            if exists:
                continue
            listing = models.Listing(
                seller_id=seller.id,
                kind="product",
                title=product["title"],
                description=product["description"],
                category=product["category"],
                price=product["price"],
                currency="NGN",
                condition_status=product["condition"],
                stock=product["stock"],
                rating_avg=4.2 + (i % 5) * 0.1,
                rating_count=5 + i * 4,
            )
            db.add(listing)
            print(f"Created product: {product['title']}")

        if buyer:
            for req in SAMPLE_REQUESTS:
                exists = db.query(models.Listing).filter(models.Listing.title == req["title"]).first()
                if exists:
                    continue
                listing = models.Listing(
                    seller_id=buyer.id,
                    kind="request",
                    title=req["title"],
                    description=req["description"],
                    category=req["category"],
                    price=req["price"],
                    currency="NGN",
                )
                db.add(listing)
                print(f"Created request: {req['title']}")

        db.commit()
        print("\nDone seeding sample data.")
    finally:
        db.close()


if __name__ == "__main__":
    run()
