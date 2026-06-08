"""Stage 2: company domain -> verified Person records via Hunter.io."""
from __future__ import annotations
import json
import time
import pathlib
import requests
from stages.prospeo import Person

CACHE_DIR = pathlib.Path("cache")
SEARCH_URL = "https://api.hunter.io/v2/domain-search"
MAX_PEOPLE = 2
MAX_RETRIES = 3
MIN_CONFIDENCE = 70


def find_people(domain: str) -> list[Person]:
    """Return up to MAX_PEOPLE verified-email decision-makers at domain."""
    CACHE_DIR.mkdir(exist_ok=True)
    cache_file = CACHE_DIR / f"hunter_{domain.replace('.', '_')}.json"

    if cache_file.exists():
        print(f"  [cache] hunter people for {domain}")
        return [Person(**p) for p in json.loads(cache_file.read_text())]

    import config
    params = {
        "domain": domain,
        "api_key": config.HUNTER_API_KEY,
        "limit": 10,
        "seniority": "executive",
        "type": "personal",
    }

    emails_raw = _get(SEARCH_URL, params)
    org = emails_raw.get("organization", domain)

    seen: set[str] = set()
    people: list[Person] = []

    for e in emails_raw.get("emails", []):
        if len(people) >= MAX_PEOPLE:
            break

        email = e.get("value", "")
        if not email or email in seen:
            continue

        # drop low-confidence and explicitly invalid addresses
        if e.get("confidence", 0) < MIN_CONFIDENCE:
            continue
        verification = e.get("verification", {}) or {}
        if verification.get("status") == "invalid":
            continue

        first = e.get("first_name", "") or ""
        last = e.get("last_name", "") or ""
        full_name = f"{first} {last}".strip()
        if not full_name:
            continue

        seen.add(email)
        people.append(Person(
            name=full_name,
            first_name=first or full_name.split()[0],
            title=e.get("position", ""),
            linkedin=e.get("linkedin", "") or "",
            email=email,
            company=org,
            domain=domain,
        ))

    if people:
        from dataclasses import asdict
        cache_file.write_text(json.dumps([asdict(p) for p in people], indent=2))
    return people


def _get(url: str, params: dict) -> dict:
    """GET with retry/backoff on 429/5xx."""
    for attempt in range(MAX_RETRIES):
        try:
            resp = requests.get(url, params=params, timeout=15)
            if resp.status_code == 429:
                raise requests.HTTPError("429 Rate limit exceeded", response=resp)
            if resp.status_code in (400, 401, 403, 422):
                raise requests.HTTPError(
                    f"{resp.status_code} {resp.text[:200]}", response=resp
                )
            if resp.status_code in (500, 502, 503, 504):
                wait = 2 ** attempt
                print(f"  [hunter] {resp.status_code} – retrying in {wait}s")
                time.sleep(wait)
                continue
            resp.raise_for_status()
            return resp.json().get("data", {})
        except requests.HTTPError:
            raise
        except requests.RequestException as exc:
            if attempt == MAX_RETRIES - 1:
                raise
            wait = 2 ** attempt
            print(f"  [hunter] error {exc} – retrying in {wait}s")
            time.sleep(wait)
    return {}


if __name__ == "__main__":
    import sys
    import config
    from dataclasses import asdict
    config.load()
    domain = sys.argv[1] if len(sys.argv) > 1 else "stripe.com"
    people = find_people(domain)
    for p in people:
        print(json.dumps(asdict(p), indent=2))
