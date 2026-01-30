from database import Database, Match
from datetime import datetime, timedelta

db = Database()
session = db.get_session()

print("Seeding DB with dummy data...")

# 1. LIVE MATCH
m_live = Match(
    id="Navi_vs_Spirit_TEST",
    team1="Natus Vincere",
    team2="Team Spirit",
    league="Berserk Pro League",
    status="LIVE",
    score="1:1",
    match_time="UNKNOWN",
    map_scores={"map1": "13-11", "map2": "9-13", "map3": "4-2"},
    odds_p1=1.85,
    odds_p2=1.95
)

# 2. UPCOMING MATCH
m_up = Match(
    id="FaZe_vs_G2_TEST",
    team1="FaZe Clan",
    team2="G2 Esports",
    league="Berserk Pro League",
    status="UPCOMING",
    match_time=(datetime.now() + timedelta(hours=2)).strftime("%Y-%m-%d %H:%M"),
    odds_p1=2.10,
    odds_p2=1.75
)

# 3. FINISHED MATCH
m_fin = Match(
    id="Vitality_vs_Cloud9_TEST",
    team1="Team Vitality",
    team2="Cloud9",
    league="Berserk Pro League",
    status="FINISHED",
    score="2:0",
    match_time="2024-05-20 18:00",
    map_scores={"map1": "13-5", "map2": "13-9"},
    odds_p1=1.50,
    odds_p2=2.50
)

session.merge(m_live)
session.merge(m_up)
session.merge(m_fin)
session.commit()
session.close()

print("Data seeded! Refresh dashboard.")
