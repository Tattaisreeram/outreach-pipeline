"""Personalized email copy generator — AI-powered with template fallback."""
from __future__ import annotations
import json
import requests
from stages.prospeo import Person

_ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"

_SUBJECT_TEMPLATE = "quick question, {first_name}"

_HTML_TEMPLATE = """\
<p>Hi {first_name},</p>

<p>
I came across {company} while researching teams doing interesting work in your space —
and given your role as {title}, I wanted to reach out directly.
</p>

<p>
We help companies like yours cut the time spent on manual outreach by building
automated, personalized pipelines that surface the right prospects and send
copy that actually gets replies — without burning through a sales team's day.
</p>

<p>
Worth a 15-minute call to see if it's relevant? No deck, just a quick conversation.
</p>

<p>{sender_name}</p>
"""

_AI_PROMPT = """\
Write a cold outreach email from a founder to {name} ({title} at {company}, domain: {domain}).
Keep it under 80 words. Sound like a human peer, not a salesperson.
Return only valid JSON with keys "subject" (max 8 words) and "body" (plain text, 3 sentences max).
No HTML tags in the body."""


def build(person: Person, seed_domain: str) -> tuple[str, str]:
    """Return (subject, html_body). Tries AI copy first, falls back to template."""
    try:
        return _build_ai(person, seed_domain)
    except Exception:
        return _build_template(person)


def _build_ai(person: Person, seed_domain: str) -> tuple[str, str]:
    import config
    if not config.ANTHROPIC_API_KEY:
        raise ValueError("ANTHROPIC_API_KEY not set")

    prompt = _AI_PROMPT.format(
        name=person.first_name,
        title=person.title or "leader",
        company=person.company,
        domain=person.domain,
    )
    resp = requests.post(
        _ANTHROPIC_URL,
        headers={
            "x-api-key": config.ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": "claude-sonnet-4-6",
            "max_tokens": 300,
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout=20,
    )
    resp.raise_for_status()
    text = resp.json()["content"][0]["text"].strip()
    parsed = json.loads(text)
    subject = parsed["subject"]
    html = f"<p>Hi {person.first_name},</p>\n<p>{parsed['body']}</p>\n<p>{_sender_name()}</p>"
    return subject, html


def _build_template(person: Person) -> tuple[str, str]:
    subject = _SUBJECT_TEMPLATE.format(first_name=person.first_name)
    html = _HTML_TEMPLATE.format(
        first_name=person.first_name,
        company=person.company,
        title=person.title or "your team",
        sender_name=_sender_name(),
    )
    return subject, html


def _sender_name() -> str:
    try:
        import config
        return config.BREVO_SENDER_NAME
    except Exception:
        return "The team"
