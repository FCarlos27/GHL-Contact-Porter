import secrets
from datetime import datetime, timezone, timedelta

from services.email import send_verification_email
from services.supabase import save_verification_code

CODE_LIFETIME_MINUTES = 15


def generate_verification_code():
    return f"{secrets.randbelow(1_000_000):06d}"


def issue_verification_code(email):
    """Generate, store, and email a one-time verification code."""
    code = generate_verification_code()
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=CODE_LIFETIME_MINUTES)
    save_verification_code(email, code, expires_at)
    send_verification_email(email, code)
    return code
