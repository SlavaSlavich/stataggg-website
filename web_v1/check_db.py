from database import Database, Match

db = Database()
session = db.get_session()

total = session.query(Match).count()
print(f"Total Matches in DB: {total}")

matches = session.query(Match).all()
for m in matches:
    print(f"- {m.id} ({m.status})")

session.close()
