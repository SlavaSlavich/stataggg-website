import sys
import os

# Add parent directory to path for database import
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import config

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True, nullable=False)
    username = Column(String(100))
    first_name = Column(String(100))
    photo_url = Column(String(500))
    balance = Column(Integer, default=0)
    is_premium = Column(Boolean, default=False)
    premium_since = Column(DateTime, nullable=True)
    premium_until = Column(DateTime, nullable=True)
    is_banned = Column(Boolean, default=False)
    ban_until = Column(DateTime, nullable=True)
    is_admin = Column(Boolean, default=False)
    gift_notification = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.now)

class Database:
    def __init__(self):
        # Use SQLite database (same as web app for local development)
        # Path to the main database file
        db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'berserk_local_v2.db'))
        
        connection_string = f"sqlite:///{db_path}"
        self.engine = create_engine(connection_string, pool_pre_ping=True)
        self.SessionLocal = sessionmaker(bind=self.engine)
    
    def get_session(self):
        return self.SessionLocal()
    
    def create_tables(self):
        Base.metadata.create_all(self.engine)
