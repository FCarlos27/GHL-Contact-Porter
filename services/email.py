import os

import requests

RESEND_API_KEY = os.getenv("RESEND_API_KEY")
EMAIL_FROM = os.getenv("EMAIL_FROM", "GHL Dashboard <onboarding@resend.dev>")


def send_email(to, subject, html):
    """Send an email via the Resend API."""
    if not RESEND_API_KEY:
        raise RuntimeError("RESEND_API_KEY is not set in .env")

    response = requests.post(
        "https://api.resend.com/emails",
        headers={"Authorization": f"Bearer {RESEND_API_KEY}"},
        json={"from": EMAIL_FROM, "to": [to], "subject": subject, "html": html},
    )
    response.raise_for_status()
    return response.json()


def send_verification_email(to, code):
    subject = "Your GHL Dashboard verification code"
    html = f"""
    <p>You are registering for the GHL Dashboard.</p>
    <p>Your verification code is:</p>
    <h2 style="letter-spacing: 4px;">{code}</h2>
    <p>This code expires in 15 minutes. If you didn't request this, you can ignore this email.</p>
    """
    return send_email(to, subject, html)
