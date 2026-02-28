import re
import calendar
from datetime import datetime, time, date
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

def format_us_phone(phone:int) -> int:
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