<!-- Copilot / AI agent instructions for outreach-pipeline -->

# Outreach Pipeline — Copilot instructions

This file gives focused, actionable guidance for an AI coding agent working in this repo. Keep suggestions tightly scoped to the actual code and patterns found in the repository.

**Big Picture**
- **Purpose**: One seed domain -> lookalike companies -> decision-makers -> verified emails -> send personalized outreach via Brevo.
- **Core flow files**: `main.py` (CLI), `pipeline.py` (orchestration), `stages/` (stage implementations), `emails.py` (copy templates), `config.py` (env validation).

**Architecture & Responsibilities**
- `stages/ocean.py`: fetches lookalike company domains, caches to `cache/lookalikes_<seed>.json`.
- `stages/prospeo.py`: searches and enriches people; returns `Person` dataclass (see `stages/prospeo.Person`). Caches to `cache/people_<domain>.json`.
- `stages/brevo.py`: posts transactional email to Brevo v3 API (`/v3/smtp/email`).
- `pipeline.py`: ties stages together, dedupes by email, builds email body via `emails.build`, shows a `rich` table, and implements the send-gate.

**Run / Dev workflows**
- Create `.env` from `.env.example` and set keys: `OCEAN_API_TOKEN`, `PROSPEO_API_KEY`, `BREVO_API_KEY` (v3), `BREVO_SENDER_EMAIL`, `BREVO_SENDER_NAME`, `DEMO_RECIPIENT`.
- Setup (Windows PowerShell example):
  ```powershell
  python -m venv .venv
  .\.venv\Scripts\Activate.ps1
  pip install -r requirements.txt
  ```
- Quick runs:
  - Dry run (no sends): `python main.py stripe.com --dry-run`
  - Full dev send (safe): `python main.py stripe.com` (sends to `DEMO_RECIPIENT` unless `--send-real` is passed)
  - Production send: `python main.py stripe.com --send-real`
  - Run individual stage: `python -m stages.ocean stripe.com`, `python -m stages.prospeo stripe.com`, `python -m stages.brevo`

**Important conventions / patterns for code changes**
- Stages are independent and must be testable on their own; prefer minimal, localized edits in `stages/*`.
- All network calls use `requests` with retry/backoff on 429/5xx; preserve that pattern when adding external calls.
- Stage outputs are cached under `cache/`; read cache first and write to `cache/*.json` on fresh fetch.
- `config.load()` raises on missing env vars — call it before using any keys (pipeline does this at entry).
- Never send real emails during development. Default targets are `DEMO_RECIPIENT` unless `--send-real` passed and user confirms the gate.

**API / Integration gotchas**
- Brevo: use the **v3 API key** (header `api-key`); do not confuse with SMTP key. The sender fields come from `config.BREVO_SENDER_*`.
- Prospeo: two-step contract: `search-person` (candidates) then `enrich-person` (verified email). The code expects `only_verified_email: true` behavior.
- Ocean: POST with `apiToken` param. Limit calls and respect free-tier caps (repo docs cap to 3 companies × 2 people).

**Concrete code examples**
- To build a message: call `emails.build(person, seed_domain)` which returns `(subject, html)`.
- Person shape (fields to use): `name`, `first_name`, `title`, `linkedin`, `email`, `company`, `domain` (see `stages/prospeo.Person`).
- Cache filenames: `cache/lookalikes_<seed>.json`, `cache/people_<domain>.json` (use `domain.replace('.', '_')`).

**When editing or adding features**
- Preserve: retry/backoff logic, caching behavior, and the pipeline gate prompt flow.
- If adding new env variables, add them to `README.md` and fail-fast in `config._require` (no silent defaults).
- For changes that may send emails, default to `--dry-run` and `DEMO_RECIPIENT` in examples and tests.

If anything here is unclear or you want more detail about a particular module, tell me which file or area to expand and I'll update this file.
