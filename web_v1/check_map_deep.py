from sqlalchemy import create_engine, text

db_path = r"c:\Users\Slava\Desktop\БОТ телеграм Ставки\berserk_local_v2.db"
engine = create_engine(f"sqlite:///{db_path}")

try:
    with engine.connect() as conn:
        # Check for any map_scores that look like lists or have commas
        result = conn.execute(text("SELECT id, map_scores FROM matches WHERE map_scores LIKE '%,%' OR map_scores LIKE '%{%' LIMIT 10"))
        rows = list(result)
        if rows:
            print("Found complex map_scores:")
            for row in rows:
                print(f"{row[0]}: {row[1]}")
        else:
            print("No complex map_scores found. All look simple.")
            
        # Show a few simple ones again
        result = conn.execute(text("SELECT id, map_scores FROM matches WHERE map_scores IS NOT NULL LIMIT 5"))
        print("\nSample map_scores:")
        for row in result:
            print(f"{row[0]}: {row[1]}")

except Exception as e:
    print(f"Error: {e}")
