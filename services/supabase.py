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

def save_tokens(location_id, access_token, refresh_token, company_id=None, user_id=None):
    """Save or update tokens for a specific location."""
    data = {
        "location_id": location_id,
        "access_token": access_token,
        "refresh_token": refresh_token,
        "last_refresh": datetime.now(timezone.utc).isoformat()
    }
    if company_id:
        data["companyId"] = company_id
    if user_id:
        data["userId"] = user_id
    supabase.table(TABLE_NAME).upsert(data).execute()

def save_location_name(location_id, name):
    """Save the location's name for a specific location."""
    data = {
        "location_id": location_id,
        "name": name
    }
    supabase.table(TABLE_NAME).upsert(data).execute()

def get_user_by_email(email):
    """Return the user row for a normalized (lowercased) email, or None."""
    response = supabase.table("users").select("*").eq("email", email.lower()).limit(1).execute()
    return response.data[0] if response.data else None

def get_allowed_location_ids(user_row):
    """Return the list of location_ids a user may access."""
    if user_row.get("is_agency_owner"):
        loc_response = supabase.table("locations").select("location_id").execute()
        return [row["location_id"] for row in loc_response.data]

    response = supabase.table("user_locations").select("location_id").eq("user_id", user_row["id"]).execute()
    return [row["location_id"] for row in response.data]

def set_user_password(user_id, password_hash):
    """Set a user's password hash."""
    supabase.table("users").update({"password_hash": password_hash}).eq("id", user_id).execute()

def save_verification_code(email, code, expires_at):
    """Store a one-time verification code for an email, invalidating old ones."""
    supabase.table("email_verifications").update({"used": True}).eq("email", email).eq("used", False).execute()
    supabase.table("email_verifications").insert({
        "email": email,
        "code": code,
        "expires_at": expires_at.isoformat() if hasattr(expires_at, "isoformat") else expires_at,
    }).execute()

def get_valid_verification_code(email, code):
    """Return the latest unused, unexpired verification row for an email, or None."""
    from datetime import datetime, timezone
    response = (
        supabase.table("email_verifications")
        .select("*")
        .eq("email", email)
        .eq("code", code)
        .eq("used", False)
        .gte("expires_at", datetime.now(timezone.utc).isoformat())
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    return response.data[0] if response.data else None

def mark_verification_used(verification_id):
    """Mark a verification code as used."""
    supabase.table("email_verifications").update({"used": True}).eq("id", verification_id).execute()

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
