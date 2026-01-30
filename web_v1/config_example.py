import os

# Telegram Settings (Must match Bot)
BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"
CHANNEL_ID = "@YourChannelName"
ADMIN_IDS = [123456789]  # Replace with your Telegram ID

# Web Settings
SECRET_KEY = os.getenv("SECRET_KEY", "GENERATE_RANDOM_SECRET_KEY_HERE")

# Database Settings
# For local development (SQLite)
# DB will be auto-detected on Windows

# For production (MySQL)
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_USER = os.getenv("DB_USER", "stataggg_user")
DB_PASS = os.getenv("DB_PASS", "your_secure_password")
DB_NAME = os.getenv("DB_NAME", "stataggg_db")
