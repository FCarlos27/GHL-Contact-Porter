import re
from utils.formatting import normalize_date

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
