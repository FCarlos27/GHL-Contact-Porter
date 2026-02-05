import requests
import re
from datetime import timedelta, date, datetime, time


def compute_time_range(range_type, date_input=None):
    """Return start and end timestamps (ms) for today, tomorrow, or a specific date."""
    
    if range_type == "today":
        start = datetime.combine(date.today(), time(10))
        end = start + timedelta(hours=11)

    elif range_type == "tomorrow":
        start = datetime.combine(date.today() + timedelta(days=1), time(10))
        end = start + timedelta(hours=11)

    elif range_type == "specific":
        selected = datetime.strptime(date_input, "%Y-%m-%d").date()
        start = datetime.combine(selected, time())
        end = datetime.combine(selected, time(20))

    else:
        raise ValueError("Invalid range type")

    return int(start.timestamp() * 1000), int(end.timestamp() * 1000)

def extract_appointments(json_data):
    """Return a clean list of appointment objects ready for rendering."""
    
    descriptions = []

    for event in json_data.get("events", []):
        if event["appointmentStatus"] not in ["confirmed", "showed"]:
            continue

        notes = event.get("notes", "")
        description = clean_html_description(notes)
        descriptions.append(description)

    return descriptions

import re

def clean_html_description(notes):
    if not notes:
        return "Appointment's description is empty."

    notes = notes.strip()

    # Extract booked time
    booked_regex = re.compile(
        r"BOOKED\s+FOR\s+\w+\s+AT\s+(\d{1,2})[.:]?(\d{2})?\s*([APMapm]{0,2})",
        re.IGNORECASE
    )

    match = booked_regex.search(notes)

    if match:
        hour = int(match.group(1))
        minute = match.group(2) or "00"
        meridian = match.group(3).upper() or ""
        booked_line = f"*BOOKED FOR TODAY AT {hour}:{minute.zfill(2)} {meridian} 📌*"
    else:
        booked_line = "*BOOKED FOR TODAY 📌*"

    # Remove old formatting
    notes = re.sub(r"\*?NEW APPOINTMENT\*?", "", notes, flags=re.IGNORECASE)
    notes = re.sub(r"\*?RESCHEDULE\*?", "", notes, flags=re.IGNORECASE)
    notes = re.sub(r"[\*📌]", "", notes)
    notes = re.sub(booked_regex, booked_line, notes)

    # Clean whitespace
    notes = notes.strip()

    # Convert newlines to <br>
    notes = notes.replace("\n", "<br>")

    # Remove leading <br> so list number stays on same line
    notes = re.sub(r"^(<br>\s*)+", "", notes)

    # Build final HTML
    final = f"{notes}<br>"

    return final




