import os

# Telegram Settings (Must match Bot)
BOT_TOKEN = "8462164299:AAEsT2e1qJDktB5BsHlmCncfFeVhpCBx31E"
CHANNEL_ID = "@StatistikaBerserkCS"
ADMIN_IDS = [6616618500] 

# Web Settings
SECRET_KEY = os.getenv("SECRET_KEY", "berserk_secret_key_123") # For session/cookie signing

# Database Settings (Same as Bot)
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_USER = os.getenv("DB_USER", "admin")
DB_PASS = os.getenv("DB_PASS", "admin123")
DB_NAME = os.getenv("DB_NAME", "berserk_stats")
