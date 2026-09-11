from sqlalchemy import text
from database import engine

statements = [
    "ALTER TABLE users ADD COLUMN notify_messages BOOLEAN DEFAULT TRUE",
    "ALTER TABLE users ADD COLUMN notify_announcements BOOLEAN DEFAULT TRUE",
    "ALTER TABLE users ADD COLUMN notify_listing_activity BOOLEAN DEFAULT TRUE",
]

with engine.begin() as conn:
    for stmt in statements:
        try:
            conn.execute(text(stmt))
            print(f"OK: {stmt}")
        except Exception as e:
            print(f"SKIPPED ({e}): {stmt}")
