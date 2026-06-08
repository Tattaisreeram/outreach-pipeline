"""Stage 2: company domain -> verified Person records via Prospeo."""
from __future__ import annotations
import json
import time
import pathlib
import requests
from dataclasses import dataclass, asdict

CACHE_DIR = pathlib.Path("cache")
SEARCH_URL = "https://api.prospeo.io/search-person"
ENRICH_URL = "https://api.prospeo.io/enrich-person"
MAX_PEOPLE = 2
MAX_RETRIES = 3


@dataclass
class Person:
    name: str
    first_name: str
    title: str
    linkedin: str
    email: str
    company: str
    domain: str


def find_people(domain: str) -> list[Person]:
    """Return up to MAX_PEOPLE verified-email decision-makers at domain."""
    CACHE_DIR.mkdir(exist_ok=True)
    people_cache = CACHE_DIR / f"people_{domain.replace('.', '_')}.json"
    search_cache = CACHE_DIR / f"search_{domain.replace('.', '_')}.json"

    if people_cache.exists():
        print(f"  [cache] people for {domain}")
        return [Person(**p) for p in json.loads(people_cache.read_text())]

    import config
    headers = {
        "X-KEY": config.PROSPEO_API_KEY,
        "Content-Type": "application/json",
    }

    # search results cached separately so re-runs skip this API call
    if search_cache.exists():
        print(f"  [cache] search results for {domain}")
        results = json.loads(search_cache.read_text())
    else:
        payload = {
            "page": 1,
            "filters": {
                "company": {
                    "websites": {"include": [domain]},
                },
                "person_seniority": {
                    "include": ["C-Suite", "Vice President", "Director", "Founder/Owner"],
                },
            },
        }
        raw = _post(SEARCH_URL, payload, headers)
        results = raw.get("results", raw.get("response", []))
        if not isinstance(results, list):
            results = []
        search_cache.write_text(json.dumps(results, indent=2))

    seen_emails: set[str] = set()
    people: list[Person] = []
    enrich_attempts = 0
    max_enrich_attempts = MAX_PEOPLE * 4  # cap total attempts to avoid rate limiting

    for item in results:
        if enrich_attempts >= max_enrich_attempts:
            break
        if len(people) >= MAX_PEOPLE:
            break

        # response items may be {"person": {...}, "company": {...}} or flat
        p = item.get("person", item) if isinstance(item, dict) else {}
        company_data = item.get("company", {}) if isinstance(item, dict) else {}

        full_name = p.get("full_name", "").strip()
        if not full_name:
            first = p.get("first_name", "")
            last = p.get("last_name", "")
            full_name = f"{first} {last}".strip()
        if not full_name:
            continue

        first_name = p.get("first_name", "") or full_name.split()[0]
        title = p.get("current_job_title", "")

        # company name: prefer company object, fall back to job_history
        company_name = company_data.get("name", "")
        if not company_name:
            for job in p.get("job_history", []):
                if job.get("current"):
                    company_name = job.get("company_name", "")
                    break
        if not company_name:
            company_name = domain

        person_id = p.get("person_id", "")
        candidate = Person(
            name=full_name,
            first_name=first_name,
            title=title,
            linkedin=p.get("linkedin_url", ""),
            email="",
            company=company_name,
            domain=domain,
        )

        time.sleep(2)  # stay under Prospeo rate limit between enrich calls
        enrich_attempts += 1
        try:
            enriched = resolve_email(candidate, person_id=person_id)
        except requests.HTTPError as exc:
            if "429" in str(exc):
                print("  [prospeo] rate limited – stopping enrich, retry later")
                break
            print(f"  [prospeo] enrich error for {full_name}: {exc}")
            continue
        except Exception as exc:
            print(f"  [prospeo] enrich error for {full_name}: {exc}")
            continue

        if enriched and enriched.email and enriched.email not in seen_emails:
            seen_emails.add(enriched.email)
            people.append(enriched)
            if len(people) >= MAX_PEOPLE:
                break

    if people:
        people_cache.write_text(json.dumps([asdict(p) for p in people], indent=2))
    return people


def resolve_email(person: Person, person_id: str = "") -> Person | None:
    """Enrich person with verified email. Returns None if none found."""
    import config
    headers = {
        "X-KEY": config.PROSPEO_API_KEY,
        "Content-Type": "application/json",
    }

    # prefer linkedin_url (best match), then person_id, then name+domain
    if person.linkedin:
        data: dict = {"linkedin_url": person.linkedin}
    elif person_id:
        data = {"person_id": person_id}
    else:
        parts = person.name.split(None, 1)
        data = {
            "first_name": parts[0],
            "last_name": parts[1] if len(parts) > 1 else "",
            "company_website": person.domain,
        }

    payload = {
        "only_verified_email": True,
        "data": data,
    }

    try:
        raw = _post(ENRICH_URL, payload, headers)
    except requests.HTTPError as exc:
        # NO_MATCH is expected (no email in DB) — not a hard error
        if "NO_MATCH" in str(exc):
            return None
        raise

    response = raw.get("response", raw)
    email = ""
    if isinstance(response, dict):
        email_obj = response.get("email", {})
        if isinstance(email_obj, dict):
            email = email_obj.get("email", "") if email_obj.get("revealed") else ""
        elif isinstance(email_obj, str):
            email = email_obj

    if not email:
        return None

    return Person(
        name=person.name,
        first_name=person.first_name,
        title=person.title,
        linkedin=person.linkedin,
        email=email,
        company=person.company,
        domain=person.domain,
    )


def _post(url: str, payload: dict, headers: dict) -> dict:
    """POST with retry/backoff on 429/5xx. Raises immediately on 4xx client errors."""
    for attempt in range(MAX_RETRIES):
        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=20)
            if resp.status_code == 429:
                raise requests.HTTPError("429 Rate limit exceeded", response=resp)
            if resp.status_code in (400, 401, 403, 422):
                raise requests.HTTPError(
                    f"{resp.status_code} {resp.text[:300]}", response=resp
                )
            if resp.status_code in (500, 502, 503, 504):
                wait = 2 ** attempt
                print(f"  [prospeo] {resp.status_code} – retrying in {wait}s")
                time.sleep(wait)
                continue
            resp.raise_for_status()
            return resp.json()
        except requests.HTTPError:
            raise
        except requests.RequestException as exc:
            if attempt == MAX_RETRIES - 1:
                raise
            wait = 2 ** attempt
            print(f"  [prospeo] error {exc} – retrying in {wait}s")
            time.sleep(wait)
    return {}


if __name__ == "__main__":
    import sys
    import config
    config.load()
    domain = sys.argv[1] if len(sys.argv) > 1 else "stripe.com"
    people = find_people(domain)
    for p in people:
        print(json.dumps(asdict(p), indent=2))
