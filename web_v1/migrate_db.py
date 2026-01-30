from database import Database, User
import sqlalchemy
from sqlalchemy import text

print("Migrating Database...")
db = Database()
session = db.get_session()

# Check if columns exist, if not add them
try:
    with db.engine.connect() as conn:
        # SQLite doesn't support IF NOT EXISTS for columns easily in one go, 
        # but we can try adding them. If they exist, it will fail, which is fine.
        
        try:
            print("Adding is_premium...")
            conn.execute(text("ALTER TABLE users ADD COLUMN is_premium BOOLEAN DEFAULT 0"))
        except Exception as e:
            print(f"Skipped is_premium (probably exists): {e}")

        try:
            print("Adding premium_since...")
            conn.execute(text("ALTER TABLE users ADD COLUMN premium_since DATETIME"))
        except Exception as e:
            print(f"Skipped premium_since: {e}")

        try:
            print("Adding premium_until...")
            conn.execute(text("ALTER TABLE users ADD COLUMN premium_until DATETIME"))
        except Exception as e:
            print(f"Skipped premium_until: {e}")

    print("Migration Complete!")
except Exception as e:
    print(f"Critical Error: {e}")
