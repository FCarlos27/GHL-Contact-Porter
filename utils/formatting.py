import re

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
    # Accept both "-" and "/" by replacing slashes first
    parts = iso.replace("/", "-").split("-")
    y, m, d = parts
    return f"{int(m)}/{int(d)}/{y}"
