from sqlalchemy import text
from database import engine

with engine.begin() as conn:
    try:
        conn.execute(text("ALTER TABLE users ADD COLUMN onboarding_extra JSON NULL"))
        print("OK: onboarding_extra column added")
    except Exception as e:
        print(f"SKIPPED ({e})")
