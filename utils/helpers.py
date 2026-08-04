import calendar
import re
import secrets
import time
from collections import defaultdict
from datetime import datetime, time, date, timezone, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError, available_timezones

from googleapiclient.errors import HttpError

from services.email import send_verification_email
from services.supabase import save_verification_code

CODE_LIFETIME_MINUTES = 15
SHEET_ID_PATTERN = re.compile(r"/spreadsheets/d/([a-zA-Z0-9-_]+)")


def extract_sheet_id(url):
    """Extract the spreadsheet ID from a Google Sheets link, or None."""
    if not url:
        return None
    match = SHEET_ID_PATTERN.search(url)
    return match.group(1) if match else None


def safe_google_call(func, *args, max_retries=3, **kwargs):
    """Wraps Google API calls in an exponential backoff retry loop."""
    for i in range(max_retries):
        try:
            return func(*args, **kwargs)
        except HttpError as e:
            if e.resp.status == 429:
                wait_time = 2 ** i
                print(f"Rate limit hit. Retrying in {wait_time}s...")
                time.sleep(wait_time)
            else:
                raise e  # Raise other errors normally
    return None  # Failed after all retries


def format_us_phone(phone):
    """Formats the phone number into (xxx) xxx-xxxx"""
    digits = re.sub(r"\D", "", phone)  # keep only numbers

    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]  # remove country code

    if len(digits) != 10:
        return phone  # fallback if number is malformed

    area, prefix, line = digits[:3], digits[3:6], digits[6:]
    return f"({area}) {prefix}-{line}"


def normalize_date(iso: str) -> str:
    """Returns date string with format MM/DD/YYYY"""
    # Replace any slashes with dashes, then split by the dash
    parts = iso.replace("/", "-").split("-")

    # Ensure parts have the correct length
    if len(parts) != 3:
        raise ValueError("Invalid date format")

    y, m, d = parts

    # Return the formatted date as MM/DD/YYYY
    return f"{int(m)}/{int(d)}/{y}"


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


def build_timezone_map():
    tz_map = defaultdict(list)

    for tz in available_timezones():
        if "/" not in tz:
            continue

        region, city = tz.split("/", 1)
        tz_map[region].append(city)

    for region in tz_map:
        tz_map[region].sort()

    return dict(sorted(tz_map.items()))


def parse_date_value(value):
    """
    Parse a sheet date cell into a date object, or None.
    Handles both "MM/DD/YYYY" strings and datetime objects returned by
    Google Sheets when the column is formatted as a real date.
    """
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        try:
            return datetime.strptime(value, "%m/%d/%Y").date()
        except ValueError:
            return None
    return None


def format_date_key(value):
    """Return a sheet date cell as an 'MM/DD/YYYY' string, or None."""
    if isinstance(value, datetime):
        return value.strftime("%m/%d/%Y")
    if isinstance(value, str):
        return value.strip()
    return None


def generate_verification_code():
    return f"{secrets.randbelow(1_000_000):06d}"


def issue_verification_code(email):
    """Generate, store, and email a one-time verification code."""
    code = generate_verification_code()
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=CODE_LIFETIME_MINUTES)
    save_verification_code(email, code, expires_at)
    send_verification_email(email, code)
    return code