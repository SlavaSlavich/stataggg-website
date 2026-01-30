from sqlalchemy import create_engine, text
import json
import os

# Connect to the same DB the app uses
db_path = "berserk_local_v2.db"
# If running from web_v1, parent dir is project root
# If running from root, it's just the file.
# Try absolute path based on user info
db_path = r"c:\Users\Slava\Desktop\БОТ телеграм Ставки\berserk_local_v2.db"

engine = create_engine(f"sqlite:///{db_path}")

try:
    with engine.connect() as conn:
        result = conn.execute(text("SELECT id, team1, team2, score, map_scores FROM matches WHERE status='FINISHED' ORDER BY updated_at DESC LIMIT 5"))
        print(f"{'ID':<20} | {'Team1':<10} | {'Team2':<10} | {'Score':<5} | {'Map Scores'}")
        print("-" * 80)
        for row in result:
            ms = row[4]
            print(f"{row[0][:20]:<20} | {row[1][:10]:<10} | {row[2][:10]:<10} | {row[3]:<5} | {ms}")
except Exception as e:
    print(f"Error: {e}")
