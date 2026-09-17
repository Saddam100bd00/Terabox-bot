import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", 0))
SUPPORT_USERNAME = os.getenv("SUPPORT_USERNAME", "admin")
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///terabox.db")

MAX_FILE_SIZE_BYTES = int(os.getenv("MAX_FILE_SIZE_GB", 2)) * 1024 * 1024 * 1024
FREE_DAILY_LIMIT = int(os.getenv("FREE_DAILY_LIMIT", 5))
FREE_FILE_EXPIRY_MINUTES = int(os.getenv("FREE_FILE_EXPIRY_MINUTES", 60))

DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)
