import os

# Telegram Settings
BOT_TOKEN = "8433928737:AAF4Ik_cVUah-LhfDKMTkdZ7Vf-8WLiC3OI"  # @botproverkioplati_bot
ADMIN_IDS = [6616618500]  # Replace with your Telegram ID

# Database Settings (same as web app)
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_USER = os.getenv("DB_USER", "admin")
DB_PASS = os.getenv("DB_PASS", "admin123")
DB_NAME = os.getenv("DB_NAME", "berserk_stats")

# Logging
LOG_FILE = "payment_bot.log"
