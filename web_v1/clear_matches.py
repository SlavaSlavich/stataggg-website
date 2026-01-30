import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from bot_dota.database import Database, Match
from sqlalchemy import text  # Import text for SQL literal

def clear_all_matches():
    db = Database()
    session = db.get_session()
    
    try:
        # Delete all rows from matches table
        num_deleted = session.query(Match).delete()
        session.commit()
        print(f"Successfully deleted {num_deleted} matches from the database.")
        
        # Optional: Vacuum/Optimize if needed, but not critical for functionality
        
    except Exception as e:
        print(f"Error clearing matches: {e}")
        session.rollback()
    finally:
        session.close()

if __name__ == "__main__":
    clear_all_matches()
