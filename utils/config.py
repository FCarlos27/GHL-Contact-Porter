import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).resolve().parents[1] / ".env")

# OAuth credentials
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
REDIRECT_URI = os.getenv("REDIRECT_URI")

# API constants
TOKEN_URL = os.getenv("TOKEN_URL")

REQUIRED_CONFIG = {
    "CLIENT_ID": CLIENT_ID,
    "CLIENT_SECRET": CLIENT_SECRET,
    "REDIRECT_URI": REDIRECT_URI,
    "TOKEN_URL": TOKEN_URL,
}

MISSING_CONFIG = [name for name, value in REQUIRED_CONFIG.items() if not value]
if MISSING_CONFIG:
    raise RuntimeError(
        "Missing OAuth configuration in .env: " + ", ".join(MISSING_CONFIG)
    )
