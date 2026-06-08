# outreach-pipeline

![Python](https://img.shields.io/badge/python-3.11%2B-blue)
![CI](https://github.com/Tattaisreeram/outreach-pipeline/actions/workflows/ci.yml/badge.svg)
![License](https://img.shields.io/badge/license-MIT-green)

A fully automated cold-outreach CLI: give it one seed domain and it finds lookalike companies, surfaces decision-makers with verified emails, writes AI-personalized copy via Claude, and sends through Brevo — with one human confirmation gate before anything fires.

```
seed domain
    │
    ▼
┌─────────────┐
│  Ocean.io   │  up to 3 lookalike companies by domain similarity
└──────┬──────┘
       │ [company domains]
       ▼
┌─────────────┐
│  Hunter.io  │  domain search → executive contacts + verified emails
└──────┬──────┘
       │ [Person records]
       ▼
┌─────────────┐
│  Claude API │  AI-personalized subject + body (template fallback)
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

## Quickstart

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env   # then fill in your keys
python main.py stripe.com --dry-run
```

## .env keys

| Variable | Required | Notes |
|---|---|---|
| `OCEAN_API_TOKEN` | yes | ocean.io API token |
| `HUNTER_API_KEY` | yes | hunter.io API key (free: 25 searches/mo) |
| `BREVO_API_KEY` | yes | v3 API key — **not** the SMTP key |
| `BREVO_SENDER_EMAIL` | yes | verified sender address in Brevo |
| `BREVO_SENDER_NAME` | yes | display name for outgoing mail |
| `DEMO_RECIPIENT` | yes | safe inbox for dev sends |
| `ANTHROPIC_API_KEY` | optional | enables AI copy; falls back to template if absent |

## Run commands

```powershell
# Dry run — all stages, prints table, sends nothing
python main.py stripe.com --dry-run

# Send to your own inbox (safe default, gate required)
python main.py stripe.com

# Send to real prospect emails
python main.py stripe.com --send-real

# Limit company count
python main.py stripe.com --limit-companies 2
```

## Tests

```powershell
pytest tests/ -v
```

All 14 tests are fully mocked — no API keys needed.

## Cache

Stage outputs are written to `cache/` (git-ignored) so reruns skip API calls:

- `cache/lookalikes_<seed>.json`
- `cache/hunter_<domain>.json`

Delete a file to force a fresh fetch for that stage.

## Per-run reports

Each run writes a JSON summary to `runs/<timestamp>.json` (git-ignored) with seed domain, companies found, people found, emails sent, and status.

## Known limitations / design decisions

- **Ocean free tier** — lookalike search returns 403 on the free plan; the pipeline falls back to running on the seed domain itself.
- **Hunter free tier** — 25 domain searches/month. Each `python main.py` run uses 1 search per company (cached on rerun).
- **Brevo DKIM** — new sender domains may show `brevosend.com` in headers until DNS propagates; emails still deliver.
- **Why Hunter over Prospeo** — Hunter returns verified emails directly in the domain-search response (no separate enrich step), making it far more free-tier friendly. Prospeo's enrich endpoint has an aggressive hourly rate limit on free accounts.
- **AI copy fallback** — if `ANTHROPIC_API_KEY` is absent or the Claude call fails for any reason, the pipeline silently falls back to the built-in template so the demo never breaks.
