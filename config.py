"""Settings, read from environment variables (or a .env file)."""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

DATA_DIR = Path(os.environ.get("DATA_DIR", "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

MODEL = os.environ.get("LLA_MODEL", "gpt-4o-mini")  # update default model or set in .env
TIMEZONE = os.environ.get("TIMEZONE", "UTC")  # e.g. "Europe/London", "Asia/Tehran"
MORNING_PLAN_TIME = os.environ.get("MORNING_PLAN_TIME", "07:30")  # HH:MM, in TIMEZONE

WEB_PASSWORD = os.environ.get("WEB_PASSWORD", "")  # password for the web interface

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
ALLOWED_TELEGRAM_USER_ID = int(os.environ.get("ALLOWED_TELEGRAM_USER_ID", "0"))

ARVAN_API_KEY = os.environ.get("ARVAN_API_KEY", "")
ARVAN_BASE_URL = os.environ.get("ARVAN_BASE_URL", "https://api.arvancloudai.ir/v1")


def check_required() -> None:
    missing = [
        name
        for name, value in {
            "ARVAN_API_KEY": ARVAN_API_KEY,
            "TELEGRAM_BOT_TOKEN": TELEGRAM_BOT_TOKEN,
            "ALLOWED_TELEGRAM_USER_ID": ALLOWED_TELEGRAM_USER_ID,
        }.items()
        if not value
    ]
    if missing:
        raise RuntimeError(f"Missing settings: {', '.join(missing)}. See .env.example")
