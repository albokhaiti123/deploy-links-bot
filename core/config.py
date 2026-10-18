"""
Configuration module — loads environment variables and exposes project-wide constants.
"""

import os
import sys

from dotenv import load_dotenv

load_dotenv()

# --- Required ---
BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
ADMIN_ID: int = int(os.getenv("ADMIN_ID", "0")) if os.getenv("ADMIN_ID") else 0
BOT_USERNAME: str = os.getenv("BOT_USERNAME", "")

# --- Database ---
DB_NAME: str = os.getenv("DB_NAME", "bot.db")

# --- Validation ---
def validate_config() -> None:
    """Check that all required config values are present. Called once at startup."""
    if not BOT_TOKEN:
        print("FATAL: BOT_TOKEN is not set in .env")
        sys.exit(1)
    if not ADMIN_ID:
        print("FATAL: ADMIN_ID is not set in .env")
        sys.exit(1)
