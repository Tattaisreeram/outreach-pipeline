"""Stage 3: send a transactional email via Brevo v3 API."""
from __future__ import annotations
import time
import requests

BREVO_URL = "https://api.brevo.com/v3/smtp/email"
MAX_RETRIES = 3


def send(recipient_email: str, recipient_name: str, subject: str, html: str) -> dict:
    """Send one email. Returns Brevo response dict. Raises on failure."""
    import config
    headers = {
        "api-key": config.BREVO_API_KEY,
        "Content-Type": "application/json",
    }
    payload = {
        "sender": {
            "email": config.BREVO_SENDER_EMAIL,
            "name": config.BREVO_SENDER_NAME,
        },
        "to": [{"email": recipient_email, "name": recipient_name}],
        "subject": subject,
        "htmlContent": html,
    }
    for attempt in range(MAX_RETRIES):
        try:
            resp = requests.post(BREVO_URL, json=payload, headers=headers, timeout=15)
            if resp.status_code in (429, 500, 502, 503, 504):
                wait = 2 ** attempt
                print(f"  [brevo] {resp.status_code} – retrying in {wait}s")
                time.sleep(wait)
                continue
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as exc:
            if attempt == MAX_RETRIES - 1:
                raise
            wait = 2 ** attempt
            print(f"  [brevo] error {exc} – retrying in {wait}s")
            time.sleep(wait)
    return {}


if __name__ == "__main__":
    import config
    config.load()
    result = send(
        config.DEMO_RECIPIENT,
        "Test User",
        "Test email from outreach-pipeline",
        "<p>Hello from the pipeline self-test.</p>",
    )
    print(result)
