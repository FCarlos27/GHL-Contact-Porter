from services.gist_storage import get_tokens, get_location_data, save_location_name
import requests

def fetch_location_name(location_id):
    access, _ = get_tokens(location_id)

    url = f"https://services.leadconnectorhq.com/locations/{location_id}"
    
    payload = {}
    headers = {
        'Accept': 'application/json',
        'Version': '2021-07-28',
        'Authorization': f'Bearer {access}'
    }


    response = requests.get(url, headers=headers, data=payload)
    data = response.json()

    return data.get("location", {}).get("name")

def ensure_location_name(location_id):
    loc = get_location_data(location_id)

    if "name" not in loc:
        name = fetch_location_name(location_id)
        save_location_name(location_id, name)
        return name

    return loc["name"]

def fetch_calendar_events(location_id, calendar_id, access_token, start_time, end_time):
    """Fetch raw calendar events from GHL."""
    
    url = "https://services.leadconnectorhq.com/calendars/events"

    params = {
        "locationId": location_id,
        "calendarId": calendar_id,
        "startTime": start_time,
        "endTime": end_time
    }

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Version": "2021-04-15",
        "Accept": "application/json"
    }

    return requests.get(url, headers=headers, params=params)

