from services.supabase import get_tokens, get_location_data, save_location_name
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

def fetch_contacts_by_appointment_data(location_id, start, end, access_token):
    """Fetch contacts whose last appointment falls within a date range."""

    url = "https://services.leadconnectorhq.com/contacts/search"

    payload = {
        "locationId": location_id,
        "page": 1,
        "pageLimit": 40,
        "filters": [
            {
                "field": "lastAppointment",
                "operator": "range",
                "value": {
                    "gt": start,
                    "lt": end
                }
            }
        ]
    }

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {access_token}"
    }

    return requests.post(url, headers=headers, json=payload)



