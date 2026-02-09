import requests
from utils.config import CLIENT_ID, CLIENT_SECRET, REDIRECT_URI, TOKEN_URL

from services.gist_storage import (
    get_tokens,
    save_tokens,
)

def exchange_code_for_tokens(code):
    """ 
    Exchange the authorization code for access + refresh tokens.
    Used only during the OAuth callback.
    """

    payload = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI,
        "user_type": "Location"
    }

    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json"
    }

    response = requests.post(TOKEN_URL, data=payload, headers=headers)
    response.raise_for_status()

    data = response.json()

    return data.get("locationId"), data.get("access_token"), data.get("refresh_token")


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
    Refresh the token for a location and update the Gist.
    Returns the new access token.
    """
    if not refresh_token:
        raise Exception(f"No refresh token found for location {location_id}")

    new_access, new_refresh = refresh_access_token(refresh_token)

    # Save both tokens back to Gist
    save_tokens(location_id, new_access, new_refresh)

    return new_access

