import re
import calendar
from datetime import datetime, time, date
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from utils.formatting import normalize_date


def compute_time_range(date_input: str, tz: str = "UTC", mode: str = "day"  # "day" or "month"
) -> tuple[int, int]:
    """
    Returns (start_ms, end_ms) for a given day or month.
    
    date_input:
        - day mode:   "YYYY-MM-DD"
        - month mode: "YYYY-MM"
    """

    try:
        zone = ZoneInfo(tz)
    except ZoneInfoNotFoundError:
        raise ValueError(
            f"Timezone '{tz}' not found. On Windows run: pip install tzdata"
        )

    try:
        if mode == "day":
            selected = datetime.strptime(date_input, "%Y-%m-%d").date()
            start_date = selected
            end_date = selected

        elif mode == "month":
            year, month = map(int, date_input.split("-"))
            start_date = date(year, month, 1)
            last_day = calendar.monthrange(year, month)[1]
            end_date = date(year, month, last_day)

        else:
            raise ValueError("mode must be 'day' or 'month'")

    except Exception:
        raise ValueError(
            "Invalid date format. Use YYYY-MM-DD for day or YYYY-MM for month"
        )

    start = datetime.combine(start_date, time(0, 0, 0), tzinfo=zone)
    end = datetime.combine(end_date, time(23, 59, 59, 999000), tzinfo=zone)

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

def extract_contacts_scheduled(json_data, month=False):
    """Return list of contacts scheduled for a date or month"""
    contacts = []

    for event in json_data.get("events", []):
        if event["appointmentStatus"] not in ["confirmed", "showed"]:
            continue

        notes = event.get("notes", "")
        endTime = event.get("endTime", "")
        extracted = extract_contact_from_notes(notes, endTime) if month else extract_contact_from_notes(notes) 

        # Only append if at least name or phone exists
        if extracted["name"] or extracted["phone"]:
            contacts.append(extracted)

    return contacts

def extract_contact_from_notes(notes: str, date: str | None = None) -> dict:
    """Return the client's name and phone from an appointment's description, appends date if passed else None"""
    
    if not notes:
        return {"name": None, "phone": None, "date": None}

    lines = [line.strip() for line in notes.split("\n") if line.strip()]

    if lines and re.fullmatch(r"\*?NEW APPOINTMENT\*?", lines[0], re.IGNORECASE):
        lines = lines[1:]

    name = lines[0] if lines else None

    phone_regex = re.compile(r"\+?\(?\d[\d\-\s\(\)]{7,}\d")
    phone = None
    for line in lines:
        m = phone_regex.search(line)
        if m:
            phone = m.group(0)
            break

    normalized_date = None
    if date:
        normalized_date = normalize_date(date.split("T")[0])

    return {
        "name": name,
        "phone": phone,
        "date": normalized_date
    }


def format_us_phone(phone:int) -> int:
    """Formats the phone number into (xxx) xxx-xxxx"""
    digits = re.sub(r"\D", "", phone)  # keep only numbers

    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]  # remove country code

    if len(digits) != 10:
        return phone  # fallback if number is malformed

    area, prefix, line = digits[:3], digits[3:6], digits[6:]
    return f"({area}) {prefix}-{line}"









