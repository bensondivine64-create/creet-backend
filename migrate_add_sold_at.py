from sqlalchemy import text
from database import engine

with engine.begin() as conn:
    conn.execute(text("ALTER TABLE listings ADD COLUMN sold_at DATETIME NULL"))
    print("Migration complete: sold_at column added.")
