from database import Database
from sqlalchemy import text

print("🚑 Starting Database Repair...")
db = Database()

try:
    # Use engine.begin() to automatically commit the transaction
    with db.engine.begin() as conn:
        print("Checking columns...")
        
        # Try adding columns one by one. 
        # SQLite will throw an error if column exists, which we catch.
        
        try:
            conn.execute(text("ALTER TABLE users ADD COLUMN is_premium BOOLEAN DEFAULT 0"))
            print("✅ Added 'is_premium'")
        except Exception as e:
            print(f"ℹ️ 'is_premium' exists or error: {e}")

        try:
            conn.execute(text("ALTER TABLE users ADD COLUMN premium_since DATETIME"))
            print("✅ Added 'premium_since'")
        except Exception as e:
            print(f"ℹ️ 'premium_since' exists or error: {e}")

        try:
            conn.execute(text("ALTER TABLE users ADD COLUMN premium_until DATETIME"))
            print("✅ Added 'premium_until'")
        except Exception as e:
            print(f"ℹ️ 'premium_until' exists or error: {e}")

    print("🎉 Database Repair Complete!")

except Exception as e:
    print(f"❌ COSTAL ERROR: {e}")
