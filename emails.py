"""Personalized email copy generator."""
from __future__ import annotations
from stages.prospeo import Person

_SUBJECT_TEMPLATES = [
    "quick question, {first_name}",
    "{first_name} – idea for {company}",
    "for {first_name} at {company}",
]

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

<p>
{sender_name}
</p>
"""


def build(person: Person, seed_domain: str) -> tuple[str, str]:
    """Return (subject, html_body) personalized for person."""
    subject = _SUBJECT_TEMPLATES[0].format(
        first_name=person.first_name,
        company=person.company,
    )
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
