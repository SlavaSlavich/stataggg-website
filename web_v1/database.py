from sqlalchemy import create_engine, Column, String, Integer, Float, DateTime, Enum, JSON, Boolean, BigInteger, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import config

Base = declarative_base()

# --- MODELS ---

class User(Base):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    telegram_id = Column(BigInteger, unique=True, index=True)
    username = Column(String(100), nullable=True)
    first_name = Column(String(100), nullable=True)
    photo_url = Column(String(500), nullable=True)
    
    balance = Column(Float, default=0.0)
    is_premium = Column(Boolean, default=False)
    premium_since = Column(DateTime, nullable=True)
    premium_until = Column(DateTime, nullable=True)
    is_admin = Column(Boolean, default=False)
    is_banned = Column(Boolean, default=False)
    ban_until = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    gift_notification = Column(String(500), nullable=True)

class ChatMessage(Base):
    __tablename__ = 'chat_messages'
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    content = Column(String(1000), nullable=False)
    reply_to_id = Column(Integer, ForeignKey('chat_messages.id'), nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    is_edited = Column(Boolean, default=False)
    
    user = relationship("User", backref="messages")
    reply_to = relationship("ChatMessage", remote_side=[id], backref="replies")

class Match(Base):
    __tablename__ = 'matches'
    
    id = Column(String(255), primary_key=True) # ID format: "Team1_vs_Team2_Time"
    game_type = Column(String(50), default="CS2") # Added for Unified DB (CS2/DOTA2)
    league = Column(String(100), default="Berserk League")
    team1 = Column(String(100))
    team2 = Column(String(100))
    match_time = Column(String(50)) 
    status = Column(Enum('UPCOMING', 'LIVE', 'FINISHED', name='match_status'))
    score = Column(String(50), default="0:0")
    map_scores = Column(JSON, nullable=True)
    odds_p1 = Column(Float, default=0.0)
    odds_p2 = Column(Float, default=0.0)
    winner = Column(String(100), nullable=True)
    message_id = Column(Integer, nullable=True)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

class Discipline(Base):
    __tablename__ = 'disciplines'
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False) # e.g. "CS2", "Dota 2"
    image_url = Column(String(500), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.now)
    
    channels = relationship("StreamChannel", back_populates="discipline", cascade="all, delete-orphan")

class StreamChannel(Base):
    __tablename__ = 'stream_channels'
    
    id = Column(Integer, primary_key=True, index=True)
    discipline_id = Column(Integer, ForeignKey('disciplines.id'))
    name = Column(String(100), nullable=False) # Channel Name
    stream_url = Column(String(500), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.now)
    
    discipline = relationship("Discipline", back_populates="channels")

# --- DATABASE CLASS ---

class Database:
    def __init__(self):
        # Fallback to SQLite (Local Dev)
        import sys
        import os
        if sys.platform == "win32":
            # Resolve path relative to THIS file (web_v1/database.py)
            # We want the DB to be in the project root (one level up)
            current_dir = os.path.dirname(os.path.abspath(__file__))
            project_root = os.path.dirname(current_dir)
            db_path = os.path.join(project_root, "berserk_local_v2.db")
            self.url = f"sqlite:///{db_path}"
        else:
            self.url = f"mysql+pymysql://{config.DB_USER}:{config.DB_PASS}@{config.DB_HOST}/{config.DB_NAME}"
        
        self.engine = create_engine(self.url, pool_recycle=3600)
        Base.metadata.create_all(self.engine) # Auto-create tables for Main DB (Users)
        self.Session = sessionmaker(bind=self.engine)
        
        # --- CONNECT TO BOT DATABASES (Read-Only theoretically, but we use standard session) ---
        if sys.platform == "win32":
            cs2_path = os.path.join(project_root, "berserk_cs2_v2.db")
            dota_path = os.path.join(project_root, "berserk_dota_v2.db")
            
            self.engine_cs2 = create_engine(f"sqlite:///{cs2_path}")
            self.engine_dota = create_engine(f"sqlite:///{dota_path}")
            
            self.SessionCS2 = sessionmaker(bind=self.engine_cs2)
            self.SessionDota = sessionmaker(bind=self.engine_dota)
        else:
            # Prod environment (MySQL) - Assuming bots use same DB or separate?
            # For now, let's assume separate DBs on same host if configured, or just same DB.
            # If everything is properly separated in models (CS2 vs Dota tables?), 
            # but we use 'game_type' distinciton in 'matches' table.
            # Users request implies separate DB FILES. On MySQL usually separate SCHEMAS.
            # Fallback for now: Use same URL (if single DB on server) or skip if strictly file-based.
            # Assuming Local Dev for this task context.
            pass

    def get_session(self):
        return self.Session()
        
    def get_cs2_session(self):
        if hasattr(self, 'SessionCS2'): return self.SessionCS2()
        return self.Session() # Fallback

    def get_dota_session(self):
        if hasattr(self, 'SessionDota'): return self.SessionDota()
        return self.Session() # Fallback

    # --- AGGREGATION METHODS ---

    def get_finished_matches_paginated(self, skip=0, limit=10):
        """Fetches finished matches from BOTH databases, sorts by time, and paginates."""
        matches = []
        
        # CS2 Matches
        s_cs2 = self.get_cs2_session()
        try:
            m_cs2 = s_cs2.query(Match).filter_by(status='FINISHED').all()
            for m in m_cs2:
                # Force branding for any match from CS2 database
                m.league_name = "1x1 CS2 Berserk League"
            matches.extend(m_cs2)
        except: pass
        finally: s_cs2.close()
        
        # Dota Matches
        s_dota = self.get_dota_session()
        try:
            m_dota = s_dota.query(Match).filter_by(status='FINISHED').all()
            for m in m_dota:
                # Force branding for any match from Dota database
                m.league_name = "1x1 Dota2 Berserk League"
            matches.extend(m_dota)
        except: pass
        finally: s_dota.close()
        
        # Sort desc
        def sort_key(m):
            try:
                # Try datetime
                if isinstance(m.match_time, datetime): return m.match_time
                # Try parsing
                if len(str(m.match_time)) > 10:
                     return datetime.strptime(str(m.match_time), '%Y-%m-%d %H:%M:%S')
                return datetime.strptime(str(m.match_time), '%Y-%m-%d %H:%M')
            except:
                return datetime.min

        matches.sort(key=sort_key, reverse=True)
        
        # Paginate
        return matches[skip : skip + limit]

    def get_team_matches(self, team_name):
        """Fetches all finished matches for a team from ALL DBs."""
        matches = []
        from sqlalchemy import or_
        
        # CS2
        s_cs2 = self.get_cs2_session()
        try:
            m = s_cs2.query(Match).filter(or_(Match.team1 == team_name, Match.team2 == team_name)).filter_by(status='FINISHED').all()
            for item in m:
                item.league_name = "1x1 CS2 Berserk League"
            matches.extend(m)
        except: pass
        finally: s_cs2.close()

        # Dota
        s_dota = self.get_dota_session()
        try:
            m = s_dota.query(Match).filter(or_(Match.team1 == team_name, Match.team2 == team_name)).filter_by(status='FINISHED').all()
            for item in m:
                item.league_name = "1x1 Dota2 Berserk League"
            matches.extend(m)
        except: pass
        finally: s_dota.close()
        
        return matches
