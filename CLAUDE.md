# Outreach Pipeline — build context

CLI: one seed domain in -> lookalike companies -> decision-makers ->
verified emails -> personalized outreach sent via Brevo. Zero manual steps
after input, except ONE confirmation gate before emails fire.

## Stack
Python 3.11+, requests, python-dotenv, rich. No web frameworks. Run with `python`.

## Architecture — stages must stay independently testable
- config.py        : load .env, fail loudly if a key is missing
- stages/ocean.py    : seed_domain -> [company_domain]        (lookalikes)
- stages/prospeo.py  : company_domain -> [Person{name,title,linkedin,email}]
- stages/brevo.py    : Person + copy -> send result
- emails.py        : personalized copy template
- pipeline.py      : orchestrate, cache, dedupe, summary table, gate
- main.py          : argparse CLI entrypoint

## API contracts (VERIFIED June 2026 — Prospeo's old endpoints are dead. read live docs for body details)
- Ocean: POST https://api.ocean.io/v2/search/companies?apiToken=KEY
  body {"size":N,"companiesFilters":{"lookalikeDomains":[seed],"minScore":0.85}}
  -> companies[].domain
- Prospeo (header X-KEY):
  - POST https://api.prospeo.io/search-person  (filter company domain +
    seniority C-Level/VP/Director) -> people: name, title, linkedin url
  - POST https://api.prospeo.io/enrich-person
    body {"only_verified_email":true,"data":{"full_name":N,"company_website":D}}
    -> verified email (no credit charged when none found)
- Brevo (header api-key = v3 API key, NOT the SMTP key):
  POST https://api.brevo.com/v3/smtp/email
  body {"sender":{email,name},"to":[{email,name}],"subject","htmlContent"}

## Hard limits — free tiers are tiny, DO NOT burn credits
- Cap top 3 lookalike companies, top 2 people each (~6 enrichments max).
- Cache every stage's output to cache/*.json; on rerun, read cache first.
- --dry-run flag: run all stages, print summary, send NOTHING.
- Default send target = DEMO_RECIPIENT. --send-real to actually mail prospects.
- Gate: print rich table (company,name,title,email,subject) then
  prompt "Send N emails? [y/N]". Only y proceeds.

## Resilience (graded)
- Per company/person try/except: skip + log on failure, run continues.
- Retry w/ backoff on 429/5xx (max 3). Dedupe people by email.
- Drop anyone with no verified email; never send to a blank address.

## Never
- No real cold emails during dev — always --dry-run or DEMO_RECIPIENT.
- No keys in code or git.
