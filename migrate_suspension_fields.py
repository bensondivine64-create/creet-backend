from sqlalchemy import text
from database import engine

statements = [
    "ALTER TABLE users ADD COLUMN suspension_type VARCHAR(10) NULL",
    "ALTER TABLE users ADD COLUMN suspension_until DATETIME NULL",
    "ALTER TABLE users ADD COLUMN suspension_reason TEXT NULL",
    "ALTER TABLE users ADD COLUMN suspension_count INTEGER DEFAULT 0",
]

with engine.begin() as conn:
    for stmt in statements:
        try:
            conn.execute(text(stmt))
            print(f"OK: {stmt}")
        except Exception as e:
            print(f"SKIPPED ({e}): {stmt}")
