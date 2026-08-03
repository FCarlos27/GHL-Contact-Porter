from flask import Blueprint, request

from services.oauth import exchange_code_for_credentials, get_company_locations
from services.supabase import save_tokens, save_location_name
from services.ghl_api import ensure_location_name, fetch_ghl_users
from services.ghl_user_sync import sync_ghl_users

oauth_bp = Blueprint("oauth", __name__)


def _sync_users(access, company_id, location_id=None):
    payload = fetch_ghl_users(access, company_id, location_id)
    return sync_ghl_users(payload)


@oauth_bp.route("/oauth/callback")
def oauth_callback():
    code = request.args.get("code")
    # Get credentials (tokens, locationId, companyId) from GHL
    credentials = exchange_code_for_credentials(code)

    access = credentials.get("accessToken")
    refresh = credentials.get("refreshToken")
    location_id = credentials.get("locationId")
    company_id = credentials.get("companyId")
    user_id = credentials.get("userId")

    if location_id:
        # Single-location install
        save_tokens(location_id, access, refresh, company_id, user_id)
        ensure_location_name(location_id)
        # Sync the users for this location
        user_ids = _sync_users(access, company_id, location_id)
        return f"App installed successfully for location: {location_id} ({len(user_ids)} users synced)"

    # Company-level install: save tokens for every accessible location
    locations = get_company_locations(access)
    for loc in locations:
        save_tokens(loc["id"], access, refresh, company_id, user_id)
        save_location_name(loc["id"], loc["name"])

    # Sync all users across the company
    user_ids = _sync_users(access, company_id)
    return f"App installed successfully for {len(locations)} locations. ({len(user_ids)} users synced)"
