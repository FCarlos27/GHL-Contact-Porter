import requests
import json
from utils.config import GIST_TOKEN, GIST_ID

# -----------------------------
# Internal helpers
# -----------------------------

def _get_gist():
    """Retrieve and parse the JSON content of the Gist."""
    url = f"https://api.github.com/gists/{GIST_ID}"

    headers = {
        "Authorization": f"Bearer {GIST_TOKEN}",
        "Accept": "application/vnd.github+json"
    }

    response = requests.get(url, headers=headers)
    response.raise_for_status()

    files = response.json().get("files", {})
    content = files.get("tokens.json", {}).get("content", "{}")

    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return {}


def _update_gist(data):
    """Write updated JSON back to the Gist."""
    url = f"https://api.github.com/gists/{GIST_ID}"

    headers = {
        "Authorization": f"Bearer {GIST_TOKEN}",
        "Accept": "application/vnd.github+json"
    }

    payload = {
        "files": {
            "tokens.json": {
                "content": json.dumps(data, indent=4)
            }
        }
    }

    response = requests.patch(url, headers=headers, json=payload)
    response.raise_for_status()
    return response.json()


# -----------------------------
# Public API
# -----------------------------

def get_all_location_ids():
    """Return all the location IDs stored."""
    data = _get_gist()
    return list(data.keys())

def get_location_data(location_id):
    """
    Return the full stored object for a location:
    {
        "access_token": "...",
        "refresh_token": "...",
        "...":"..."
    }
    """
    data = _get_gist()
    return data.get(location_id, {})

def get_tokens(location_id):
    """Return (access_token, refresh_token) for a location."""
    loc = get_location_data(location_id)
    return loc.get("access_token"), loc.get("refresh_token")


def get_calendar_id(location_id):
    """Return the calendar ID for a location."""
    loc = get_location_data(location_id)
    return loc.get("calendar_id")


def save_tokens(location_id, access_token, refresh_token):
    """Save or update tokens for a specific location."""
    data = _get_gist()

    if location_id not in data:
        data[location_id] = {}

    data[location_id]["access_token"] = access_token
    data[location_id]["refresh_token"] = refresh_token

    _update_gist(data)

def save_calendar_id(location_id, calendar_id):
    """Save or update the calendar ID for a specific location."""
    data = _get_gist()

    if location_id not in data:
        data[location_id] = {}

    data[location_id]["calendar_id"] = calendar_id

    _update_gist(data)

def save_location_name(location_id, name):
    """Save the location's name for a specific location."""
    data = _get_gist()

    if location_id not in data:
        data[location_id] = {}

    data[location_id]["name"] = name
    _update_gist(data)

def update_access_token(location_id, new_access_token):
    """Update only the access token after a refresh."""
    data = _get_gist()

    if location_id not in data:
        data[location_id] = {}

    data[location_id]["access_token"] = new_access_token

    _update_gist(data)
