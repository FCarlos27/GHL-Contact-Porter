from datetime import datetime, timezone

from services.supabase import supabase

USERS_TABLE = "users"
USER_LOCATIONS_TABLE = "user_locations"
LOCATIONS_TABLE = "locations"


def _parse_user(user_data):
    """Normalize a GHL user payload into the fields we store."""
    roles = user_data.get("roles") or {}
    raw_location_ids = list(roles.get("locationIds") or [])

    # An Agency Owner (or a user with no locationIds) has access to ALL locations.
    is_agency_owner = bool(user_data.get("isAgencyOwner")) or not raw_location_ids

    return {
        "ghl_user_id": user_data.get("id"),
        "email": (user_data.get("email") or "").lower(),
        "first_name": user_data.get("firstName"),
        "last_name": user_data.get("lastName"),
        "is_agency_owner": is_agency_owner,
        "location_ids": [] if is_agency_owner else raw_location_ids,
    }


def _get_existing_user_id(ghl_user_id, email):
    """Return the internal user id matching ghl_user_id or email, if any."""
    response = supabase.table(USERS_TABLE).select("id").eq("ghl_user_id", ghl_user_id).limit(1).execute()
    if response.data:
        return response.data[0]["id"]

    response = supabase.table(USERS_TABLE).select("id").eq("email", email).limit(1).execute()
    if response.data:
        return response.data[0]["id"]

    return None


def _upsert_user(user_data):
    """Insert or update a user row, returning (user_id, location_ids, is_agency_owner)."""
    parsed = _parse_user(user_data)
    now = datetime.now(timezone.utc).isoformat()

    fields = {
        "ghl_user_id": parsed["ghl_user_id"],
        "email": parsed["email"],
        "first_name": parsed["first_name"],
        "last_name": parsed["last_name"],
        "is_agency_owner": parsed["is_agency_owner"],
        "updated_at": now,
    }

    user_id = _get_existing_user_id(parsed["ghl_user_id"], parsed["email"])
    if user_id:
        supabase.table(USERS_TABLE).update(fields).eq("id", user_id).execute()
    else:
        fields["created_at"] = now
        response = supabase.table(USERS_TABLE).insert(fields).execute()
        user_id = response.data[0]["id"]

    return user_id, parsed["location_ids"], parsed["is_agency_owner"]


def _set_user_locations(user_id, location_ids, is_agency_owner):
    """Replace a user's location mappings, expanding agency owners to all locations."""
    supabase.table(USER_LOCATIONS_TABLE).delete().eq("user_id", user_id).execute()

    if is_agency_owner:
        loc_response = supabase.table(LOCATIONS_TABLE).select("location_id").execute()
        location_ids = [row["location_id"] for row in loc_response.data]

    if location_ids:
        rows = [{"user_id": user_id, "location_id": loc_id} for loc_id in location_ids]
        supabase.table(USER_LOCATIONS_TABLE).insert(rows).execute()


def sync_ghl_users(payload_data):
    """
    Parse the GHL users payload and upsert each user into the database.
    Returns the list of internal user ids that were synced.
    """
    synced_ids = []
    users = (payload_data or {}).get("users", [])

    for user_data in users:
        user_id, location_ids, is_agency_owner = _upsert_user(user_data)
        _set_user_locations(user_id, location_ids, is_agency_owner)
        synced_ids.append(user_id)

    return synced_ids
