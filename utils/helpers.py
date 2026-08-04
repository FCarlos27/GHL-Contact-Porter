import re
import time
from googleapiclient.errors import HttpError

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
                raise e # Raise other errors normally
    return None # Failed after all retries
