import os
from pathlib import Path
from dotenv import load_dotenv
from supabase import create_client
from datetime import datetime, timezone, timedelta

load_dotenv(dotenv_path=Path(__file__).resolve().parents[1] / ".env")

for proxy_var in ["HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"]:
    os.environ.pop(proxy_var, None)

# -----------------------------
# Supabase Configuration
# -----------------------------
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("Supabase credentials not found in environment variables.")

try:
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
except ImportError as exc:
    raise RuntimeError(
        "Supabase client initialization failed. Install the missing proxy dependency with 'pip install httpx[socks]' or disable proxy settings."
    ) from exc

TABLE_NAME = "locations"

# -----------------------------
# Public API
# -----------------------------

def get_all_locations_name_id():
    """Return a list of {'id': ..., 'name': ...} for all stored locations."""
    # Only pull the exact columns we need
    response = supabase.table(TABLE_NAME).select("location_id, name").execute()

    locations = []
    for row in response.data:
        locations.append({
            "id": row.get("location_id"),
            "name": row.get("name", "Unknown")
        })
    return locations

def get_location_data(location_id):
    """Return the full stored object for a location."""
    response = supabase.table(TABLE_NAME).select("*").eq("location_id", location_id).execute()
    return response.data[0] if response.data else {}

def get_tokens(location_id):
    """Return (access_token, refresh_token) for a location."""
    loc = get_location_data(location_id)
    return loc.get("access_token"), loc.get("refresh_token")

def save_tokens(location_id, access_token, refresh_token):
    """Save or update tokens for a specific location."""
    data = {
        "location_id": location_id,
        "access_token": access_token,
        "refresh_token": refresh_token,
        "last_refresh": datetime.now(timezone.utc).isoformat()
    }
    supabase.table(TABLE_NAME).upsert(data).execute()

def save_location_name(location_id, name):
    """Save the location's name for a specific location."""
    data = {
        "location_id": location_id,
        "name": name
    }
    supabase.table(TABLE_NAME).upsert(data).execute()

def token_is_stale(last_refresh):
    """
    Check if the token is older than 24 hours.
    Supabase returns timestamptz as an ISO string.
    """
    if not last_refresh:
        return True

    try:
        # If last_refresh is already a datetime object
        if isinstance(last_refresh, datetime):
            last = last_refresh
        else:
            # Parse the ISO string from Supabase
            last = datetime.fromisoformat(last_refresh.replace('Z', '+00:00'))
    except (ValueError, AttributeError):
        return True

    now = datetime.now(timezone.utc)

    return now - last > timedelta(hours=24)
