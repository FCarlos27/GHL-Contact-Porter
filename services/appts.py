import re
from datetime import datetime, time
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

def compute_time_range(date_input=str, tz: str="UTC") -> tuple[int, int]:
    """Returns the start time and end time for the GHL API payload."""
    try:
        selected = datetime.strptime(date_input, "%Y-%m-%d").date()
        zone = ZoneInfo(tz)
    except ZoneInfoNotFoundError:
        raise ValueError(
            f"Timezone '{tz}' not found. On Windows run: pip install tzdata"
        )
    except Exception:
        raise ValueError("Invalid date format. Use YYYY-MM-DD")

    start = datetime.combine(selected, time(0, 0, 0), tzinfo=zone)
    end = datetime.combine(selected, time(23, 59, 59, 999000), tzinfo=zone)

    return int(start.timestamp() * 1000), int(end.timestamp() * 1000)

def create_appointments_html(json_data):
    """Return a clean list of appointment objects ready for rendering."""
    
    descriptions = []

    for event in json_data.get("events", []):
        if event["appointmentStatus"] not in ["confirmed", "showed"]:
            continue

        notes = event.get("notes", "")
        description = clean_html_description(notes)
        descriptions.append(description)

    return descriptions

def clean_html_description(notes):
    """Returns and HTML string following a given pattern"""
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

def extract_contacts_scheduled(json_data):
    """Return list of contacts scheduled for a date"""
    contacts = []

    for event in json_data.get("events", []):
        if event["appointmentStatus"] not in ["confirmed", "showed"]:
            continue

        notes = event.get("notes", "")
        extracted = extract_contact_from_appointment(notes)

        # Only append if at least name or phone exists
        if extracted["name"] or extracted["phone"]:
            contacts.append(extracted)

    return contacts

def extract_contact_from_appointment(notes: str) -> dict:
    """Return the client's name and phone from an appointment description"""

    if not notes:
        return {"name": None, "phone": None}

    # Split into non-empty trimmed lines
    lines = [line.strip() for line in notes.split("\n") if line.strip()]

    # Remove optional NEW APPOINTMENT line
    if lines and re.fullmatch(r"\*?NEW APPOINTMENT\*?", lines[0], re.IGNORECASE):
        lines = lines[1:]

    # Name = first remaining line
    name = lines[0] if lines else None

    # Phone regex
    phone_regex = re.compile(r"\+?\(?\d[\d\-\s\(\)]{7,}\d")
    phone = None 
    for line in lines: 
        m = phone_regex.search(line) 
        if m: 
            phone = m.group(0) 
            break


    return {"name": name, "phone": phone}


def format_us_phone(phone:int) -> int:
    """Formats the phone number into (xxx) xxx-xxxx"""
    digits = re.sub(r"\D", "", phone)  # keep only numbers

    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]  # remove country code

    if len(digits) != 10:
        return phone  # fallback if number is malformed

    area, prefix, line = digits[:3], digits[3:6], digits[6:]
    return f"({area}) {prefix}-{line}"









