"""Stage 1: seed domain -> list of lookalike company domains via Ocean.io."""
from __future__ import annotations
import json
import time
import pathlib
import requests

CACHE_DIR = pathlib.Path("cache")
OCEAN_URL = "https://api.ocean.io/v2/search/companies"
MAX_COMPANIES = 3
MAX_RETRIES = 3


def find_lookalikes(seed_domain: str) -> list[str]:
    """Return up to MAX_COMPANIES lookalike domains for seed_domain.

    Reads from cache if available; writes to cache on fresh fetch.
    Falls back to [seed_domain] if Ocean returns 403 (free tier restriction).
    """
    CACHE_DIR.mkdir(exist_ok=True)
    cache_file = CACHE_DIR / f"lookalikes_{seed_domain.replace('.', '_')}.json"

    if cache_file.exists():
        print(f"  [cache] lookalikes for {seed_domain}")
        return json.loads(cache_file.read_text())

    import config
    try:
        domains = _fetch(seed_domain, config.OCEAN_API_TOKEN)
    except Exception as exc:
        print(f"  [ocean] {exc}")
        print(f"  [ocean] falling back to seed domain: {seed_domain}")
        domains = [seed_domain]

    cache_file.write_text(json.dumps(domains, indent=2))
    return domains


def _fetch(seed_domain: str, api_token: str) -> list[str]:
    """Hit Ocean API with retry/backoff. Returns list of domains."""
    payload = {
        "size": MAX_COMPANIES,
        "companiesFilters": {
            "lookalikeDomains": [seed_domain],
            "minScore": 0.85,
        },
    }
    for attempt in range(MAX_RETRIES):
        try:
            resp = requests.post(
                OCEAN_URL,
                params={"apiToken": api_token},
                json=payload,
                timeout=20,
            )
            if resp.status_code == 403:
                raise requests.HTTPError(f"403 Forbidden – Ocean free tier may not include lookalikes", response=resp)
            if resp.status_code in (429, 500, 502, 503, 504):
                wait = 2 ** attempt
                print(f"  [ocean] {resp.status_code} – retrying in {wait}s")
                time.sleep(wait)
                continue
            resp.raise_for_status()
            data = resp.json()
            companies = data.get("companies", [])
            return [c["domain"] for c in companies[:MAX_COMPANIES] if c.get("domain")]
        except requests.RequestException as exc:
            if attempt == MAX_RETRIES - 1:
                raise
            wait = 2 ** attempt
            print(f"  [ocean] error {exc} – retrying in {wait}s")
            time.sleep(wait)
    return []


if __name__ == "__main__":
    import sys
    import config
    config.load()
    seed = sys.argv[1] if len(sys.argv) > 1 else "stripe.com"
    domains = find_lookalikes(seed)
    print(json.dumps(domains, indent=2))
