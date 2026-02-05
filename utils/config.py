import os
from dotenv import load_dotenv

load_dotenv()

# OAuth credentials
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
REDIRECT_URI = os.getenv("REDIRECT_URI")

# Gist storage
GIST_TOKEN = os.getenv("GIST_TOKEN")
GIST_ID = os.getenv("GIST_ID")

# Calendar + Location
LOCATION_ID = os.getenv("LOCATION_ID")
CALENDAR_ID = os.getenv("CALENDAR_ID")

# API constants
GHL_API_VERSION = "2021-04-15"
TOKEN_URL = os.getenv("TOKEN_URL")
