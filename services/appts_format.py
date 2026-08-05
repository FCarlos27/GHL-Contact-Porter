import html
import re
from utils.helpers import normalize_date

BOOKED_REGEX = re.compile(
    r"BOOKED\s+FOR\s+\w+(?:\s+\d{1,2}/\d{1,2}(?:/\d{2,4})?)?\s+AT\s+(\d{1,2})[.:]?(\d{2})?\s*([APMapm]{0,2})",
    re.IGNORECASE
)
NEW_APPOINTMENT_HEADER_REGEX = re.compile(r"\*?NEW APPOINTMENT\*?", re.IGNORECASE)
RESCHEDULE_REGEX = re.compile(r"\*?RESCHEDULE\*?", re.IGNORECASE)
PHONE_REGEX = re.compile(r"\+?\(?\d[\d\-\s\(\)]{7,}\d")
CONFIRMED_STATUSES = ("confirmed", "showed")


def _is_scheduled(event):
    """True if the event is a confirmed or showed appointment."""
    return event.get("appointmentStatus") in CONFIRMED_STATUSES


def create_appointments_html(json_data):
    """Return a clean list of appointment objects ready for rendering."""

    descriptions = []

    for event in json_data.get("events", []):
        if not _is_scheduled(event):
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

    match = BOOKED_REGEX.search(notes)

    if match:
        hour = int(match.group(1))
        minute = match.group(2) or "00"
        meridian = match.group(3).upper() or ""
        booked_line = f"*BOOKED FOR TODAY AT {hour}:{minute.zfill(2)} {meridian} 📌*"
    else:
        booked_line = "*BOOKED FOR TODAY 📌*"

    # Remove old formatting
    notes = re.sub(NEW_APPOINTMENT_HEADER_REGEX, "", notes)
    notes = re.sub(RESCHEDULE_REGEX, "", notes)
    notes = re.sub(r"[\*📌]", "", notes)
    notes = re.sub(BOOKED_REGEX, booked_line, notes)

    # Clean whitespace
    notes = notes.strip()

    # Escape any HTML in the appointment notes before converting newlines
    notes = html.escape(notes)

    # Convert newlines to <br>
    notes = notes.replace("\n", "<br>")

    # Remove leading <br> so list number stays on same line
    notes = re.sub(r"^(<br>\s*)+", "", notes)

    # Build final HTML
    final = f"{notes}<br>"

    # Ensure an "Assigned to" line is always present
    if not re.search(r"Assigned\s+to", final, re.IGNORECASE):
        final += "Assigned to: None<br>"

    return final


def extract_contacts_scheduled(json_data, month=False):
    """Returns a list of contacts scheduled for a single day or whole month"""
    contacts = []

    for event in json_data.get("events", []):
        if not _is_scheduled(event):
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

    if lines and NEW_APPOINTMENT_HEADER_REGEX.fullmatch(lines[0]):
        lines = lines[1:]

    name = lines[0] if lines else None

    phone = None
    for line in lines:
        m = PHONE_REGEX.search(line)
        if m:
            phone = m.group(0)
            break

    normalized_date = None
    if date:
        try:
            normalized_date = normalize_date(date.split("T")[0])
        except ValueError:
            normalized_date = None

    return {
        "name": name,
        "phone": phone,
        "date": normalized_date
    }
