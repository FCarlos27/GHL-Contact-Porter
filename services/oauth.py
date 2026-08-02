import requests
from utils.config import CLIENT_ID, CLIENT_SECRET, REDIRECT_URI, TOKEN_URL

from services.supabase import save_tokens


def _validate_oauth_settings():
    if not all([CLIENT_ID, CLIENT_SECRET, REDIRECT_URI, TOKEN_URL]):
        raise RuntimeError(
            "OAuth configuration is incomplete. Set CLIENT_ID, CLIENT_SECRET, REDIRECT_URI, and TOKEN_URL in your .env file."
        )


_validate_oauth_settings()

def exchange_code_for_credentials(code):
    """
    Exchange the authorization code for credentials (tokens, locationId, companyId).
    Returns the full JSON response from GHL.
    Used only during the OAuth callback.
    """

    payload = {
        "clientId": CLIENT_ID,
        "clientSecret": CLIENT_SECRET,
        "grantType": "authorization_code",
        "code": code,
        "redirectUri": REDIRECT_URI,
        "userType": "Location"
    }

    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json",
        "Version": "v3"
    }

    response = requests.post(TOKEN_URL, data=payload, headers=headers)
    if response.status_code != 200:
        raise RuntimeError(
            f"Token exchange failed with {response.status_code}: {response.text}"
        )

    return response.json()


def get_company_locations(access_token):
    """Fetch all locations accessible to a Company-level (agency) install."""
    url = "https://services.leadconnectorhq.com/locations/search"

    headers = {
        "Accept": "application/json",
        "Version": "v3",
        "Authorization": f"Bearer {access_token}"
    }

    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        raise RuntimeError(
            f"Failed to fetch locations with {response.status_code}: {response.text}"
        )

    return response.json().get("locations", [])


def refresh_access_token(refresh_token):
    """
    Refresh the access token using the refresh token.
    """

    payload = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "user_type": "Location"
    }

    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json"
    }

    response = requests.post(TOKEN_URL, data=payload, headers=headers)
    response.raise_for_status()

    data = response.json()

    return data.get("access_token"), data.get("refresh_token")


def refresh_if_needed(location_id, refresh_token):
    """
    Refresh the token for a location and update the database.
    Returns the new access token.
    """
    if not refresh_token:
        raise Exception(f"No refresh token found for location {location_id}")
    new_access, new_refresh = refresh_access_token(refresh_token)

    # Save both tokens back to the database
    save_tokens(location_id, new_access, new_refresh)

    return new_access

