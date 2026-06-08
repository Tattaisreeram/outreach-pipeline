# outreach-pipeline

One seed domain in → lookalike companies → decision-makers → verified emails → personalized outreach via Brevo. Zero manual steps after input, except one confirmation gate before emails fire.

```
seed domain
    │
    ▼
┌─────────────┐
│  Ocean.io   │  find up to 3 lookalike companies by domain
└──────┬──────┘
       │ [company domains]
       ▼
┌─────────────┐
│  Prospeo    │  search-person → C-Level/VP/Director
│             │  enrich-person → verified email only
└──────┬──────┘
       │ [Person records]
       ▼
┌─────────────┐
│  emails.py  │  build personalized subject + HTML body
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  Rich table │  company / name / title / email / subject
│  + gate     │  "Send N emails? [y/N]"
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  Brevo v3   │  POST /smtp/email → 201
└─────────────┘
```

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and fill in your keys:

```
OCEAN_API_TOKEN=
PROSPEO_API_KEY=
BREVO_API_KEY=          # v3 API key — NOT the SMTP key
BREVO_SENDER_EMAIL=you@yourdomain.com
BREVO_SENDER_NAME=Your Name
DEMO_RECIPIENT=you@yourdomain.com
```

## Smoke-test APIs before running

```powershell
# Brevo
curl.exe -s -H "api-key: $env:BREVO_API_KEY" https://api.brevo.com/v3/account

# Prospeo
curl.exe -s -X POST -H "X-KEY: $env:PROSPEO_API_KEY" -H "Content-Type: application/json" -d '{}' https://api.prospeo.io/account-information

# Ocean (paste raw key if env var not set in session)
curl.exe -s -X POST "https://api.ocean.io/v2/search/companies?apiToken=$env:OCEAN_API_TOKEN" -H "Content-Type: application/json" -d '{\"size\":1,\"companiesFilters\":{\"lookalikeDomains\":[\"stripe.com\"]}}'
```

## Run commands

```powershell
# Dry run — all stages execute, summary printed, nothing sent
python main.py stripe.com --dry-run

# Send to your DEMO_RECIPIENT inbox (safe for dev)
python main.py stripe.com

# Send to real prospect emails (production)
python main.py stripe.com --send-real

# Limit to fewer companies
python main.py stripe.com --limit-companies 2
```

## Test individual stages

```powershell
python -m stages.ocean stripe.com
python -m stages.prospeo stripe.com
python -m stages.brevo          # sends one test email to DEMO_RECIPIENT
```

## Cache

All stage outputs are written under `cache/` (git-ignored):

- `cache/lookalikes_<seed>.json`
- `cache/people_<domain>.json`

Delete a file to force a fresh API call for that stage.

## Known limitations

- **Brevo DKIM propagation** — new sender domains may route through `brevosend.com` until DNS propagates. Emails still deliver; the From header may show the rewrite.
- **Free-tier credit caps** — Prospeo free tier: ~75 enrichments. Ocean free tier: limited searches. The pipeline caps at 3 companies x 2 people = 6 enrichments max per run.
- **Ocean signup blocks** — if Ocean.io access is unavailable, replace `stages/ocean.py` with a call to Prospeo's Search Company endpoint and note it in the run.
- **Only verified emails** — Prospeo's `only_verified_email: true` means contacts without a confirmed address are silently dropped. This is intentional; it protects sender reputation.
