from sqlalchemy import text
from database import engine

statements = [
    "ALTER TABLE users ADD COLUMN last_active TIMESTAMP",
    "ALTER TABLE users ADD COLUMN hide_online_status BOOLEAN DEFAULT FALSE",
    "ALTER TABLE messages ADD COLUMN image_url VARCHAR(500)",
    "ALTER TABLE messages ALTER COLUMN content DROP NOT NULL",
]

with engine.begin() as conn:
    for stmt in statements:
        try:
            conn.execute(text(stmt))
            print(f"OK: {stmt}")
        except Exception as e:
            print(f"SKIPPED ({e}): {stmt}")
