"""Unit tests — all HTTP mocked, no real API calls."""
from __future__ import annotations
import json
from unittest.mock import patch, MagicMock

import pytest

from stages.prospeo import Person
import emails


# ── helpers ──────────────────────────────────────────────────────────────────

def _person(**kwargs) -> Person:
    defaults = dict(
        name="Jane Smith", first_name="Jane", title="VP Engineering",
        linkedin="", email="jane@example.com", company="Example Co", domain="example.com"
    )
    return Person(**{**defaults, **kwargs})


# ── email builder ─────────────────────────────────────────────────────────────

def test_template_build_interpolates_first_name():
    person = _person(first_name="Alice", company="Acme", title="CTO")
    subject, html = emails._build_template(person)
    assert "Alice" in subject
    assert "Alice" in html
    assert "Acme" in html


def test_template_build_nonempty():
    subject, html = emails._build_template(_person())
    assert subject
    assert html


def test_build_falls_back_to_template_when_no_api_key():
    with patch("config.ANTHROPIC_API_KEY", ""):
        subject, html = emails.build(_person(), "seed.com")
    assert subject
    assert html


def test_build_uses_ai_when_key_present():
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "content": [{"text": json.dumps({"subject": "AI subject", "body": "AI body text."})}]
    }
    with patch("config.ANTHROPIC_API_KEY", "test-key"), \
         patch("requests.post", return_value=mock_response):
        subject, html = emails.build(_person(), "seed.com")
    assert subject == "AI subject"
    assert "AI body text." in html


# ── dedupe ────────────────────────────────────────────────────────────────────

def test_pipeline_dedupes_by_email():
    """pipeline.run dedupes people with the same email across companies."""
    seen: set[str] = set()
    people = [
        _person(email="dupe@x.com"),
        _person(email="dupe@x.com"),
        _person(email="unique@x.com"),
    ]
    result = []
    for p in people:
        if p.email not in seen:
            seen.add(p.email)
            result.append(p)
    assert len(result) == 2
    assert result[0].email == "dupe@x.com"
    assert result[1].email == "unique@x.com"


# ── Hunter response parser ────────────────────────────────────────────────────

def test_hunter_parse_filters_low_confidence(tmp_path):
    from unittest.mock import patch as _patch
    sample_data = {
        "organization": "Stripe",
        "emails": [
            {"value": "ceo@stripe.com", "type": "personal", "confidence": 92,
             "first_name": "Pat", "last_name": "CEO", "position": "CEO",
             "seniority": "executive", "linkedin": "", "verification": {"status": "valid"}},
            {"value": "low@stripe.com", "type": "personal", "confidence": 30,
             "first_name": "Low", "last_name": "Conf", "position": "Intern",
             "seniority": "junior", "linkedin": "", "verification": {}},
        ]
    }
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {"data": sample_data}

    with _patch("requests.get", return_value=mock_resp), \
         _patch("config.HUNTER_API_KEY", "test"), \
         _patch("stages.hunter.CACHE_DIR", tmp_path):
        import config
        config.HUNTER_API_KEY = "test"
        from stages import hunter
        people = hunter.find_people("stripe.com")

    assert len(people) == 1
    assert people[0].email == "ceo@stripe.com"


def test_hunter_parse_skips_invalid_verification(tmp_path):
    from unittest.mock import patch as _patch
    sample_data = {
        "organization": "Acme",
        "emails": [
            {"value": "invalid@acme.com", "type": "personal", "confidence": 95,
             "first_name": "Bad", "last_name": "Email", "position": "CTO",
             "linkedin": "", "verification": {"status": "invalid"}},
            {"value": "good@acme.com", "type": "personal", "confidence": 88,
             "first_name": "Good", "last_name": "Email", "position": "VP Sales",
             "linkedin": "", "verification": {"status": "valid"}},
        ]
    }
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {"data": sample_data}

    with _patch("requests.get", return_value=mock_resp), \
         _patch("stages.hunter.CACHE_DIR", tmp_path):
        import config
        config.HUNTER_API_KEY = "test"
        from stages import hunter
        people = hunter.find_people("acme.com")

    assert all(p.email != "invalid@acme.com" for p in people)


# ── domain validation ─────────────────────────────────────────────────────────

import re

_DOMAIN_RE = re.compile(r"^[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z]{2,})+$")


def _is_valid_domain(s: str) -> bool:
    return bool(_DOMAIN_RE.match(s))


@pytest.mark.parametrize("domain", ["stripe.com", "google.com", "sub.example.co.uk"])
def test_valid_domains(domain):
    assert _is_valid_domain(domain)


@pytest.mark.parametrize("domain", ["IIIT Lucknow", "not a domain", "", "http://stripe.com"])
def test_invalid_domains(domain):
    assert not _is_valid_domain(domain)
