import time
from googleapiclient.errors import HttpError

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