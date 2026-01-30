from sqlalchemy import create_engine, text
import os

# DB Path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
db_path = os.path.join(project_root, "berserk_local_v2.db")
db_url = f"sqlite:///{db_path}"

print(f"Connecting to: {db_url}")

engine = create_engine(db_url)

with engine.connect() as conn:
    print("Checking 'matches' table...")
    try:
        # Check if column exists
        result = conn.execute(text("PRAGMA table_info(matches)"))
        columns = [row[1] for row in result.fetchall()]
        
        if 'game_type' not in columns:
            print("Message: Adding 'game_type' column...")
            conn.execute(text("ALTER TABLE matches ADD COLUMN game_type VARCHAR(50) DEFAULT 'CS2'"))
            conn.commit()
            print("Success: Column added.")
            
            # Update existing records to 'CS2'
            print("Updating existing records to CS2...")
            conn.execute(text("UPDATE matches SET game_type = 'CS2' WHERE game_type IS NULL"))
            conn.commit()
            print("Success: Records updated.")
        else:
            print("Info: 'game_type' column already exists.")
            
    except Exception as e:
        print(f"Error: {e}")
