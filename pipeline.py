"""Orchestrate all stages: lookalikes -> people -> emails -> gate -> send."""
from __future__ import annotations
import json
import logging
import pathlib
from dataclasses import dataclass
from datetime import datetime, timezone

from rich.console import Console
from rich.table import Table

import config
import emails
from stages import ocean, brevo
from stages import hunter
from stages.prospeo import Person

console = Console()
log = logging.getLogger("pipeline")

RUNS_DIR = pathlib.Path("runs")


@dataclass
class _Row:
    company: str
    name: str
    title: str
    email: str
    subject: str
    html: str
    person: Person


def run(
    seed_domain: str,
    dry_run: bool = True,
    send_real: bool = False,
    limit_companies: int = 3,
) -> None:
    """Full pipeline. dry_run=True skips send; send_real routes to real emails."""
    _setup_logging()
    config.load()

    report: dict = {
        "seed_domain": seed_domain,
        "dry_run": dry_run,
        "send_real": send_real,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "companies_found": [],
        "people_found": 0,
        "emails_sent": 0,
        "status": "started",
    }

    # ── Stage 1: lookalikes ───────────────────────────────────────────────────
    console.rule("[bold cyan]Stage 1 — Lookalikes")
    try:
        domains = ocean.find_lookalikes(seed_domain)
    except Exception as exc:
        log.error("Ocean stage failed: %s", exc)
        console.print(f"[red]Ocean stage failed: {exc}")
        _write_report({**report, "status": "failed", "error": str(exc)})
        return

    domains = domains[:limit_companies]
    if not domains:
        log.warning("No lookalike companies found")
        console.print("[yellow]No lookalike companies found. Exiting.")
        _write_report({**report, "status": "no_companies"})
        return

    report["companies_found"] = domains
    log.info("Found %d companies: %s", len(domains), domains)
    console.print(f"  Found {len(domains)} companies: {domains}")

    # ── Stage 2: people + email resolve ──────────────────────────────────────
    console.rule("[bold cyan]Stage 2 — People")
    rows: list[_Row] = []
    seen_emails: set[str] = set()

    for domain in domains:
        try:
            people = hunter.find_people(domain)
        except Exception as exc:
            log.warning("Skipping %s: %s", domain, exc)
            console.print(f"  [red]Skipping {domain}: {exc}")
            continue

        for person in people:
            if not person.email or person.email in seen_emails:
                continue
            seen_emails.add(person.email)
            try:
                subject, html = emails.build(person, seed_domain)
            except Exception as exc:
                log.warning("Email build failed for %s: %s", person.name, exc)
                console.print(f"  [red]Email build failed for {person.name}: {exc}")
                continue
            log.info("Queued %s <%s> at %s", person.name, person.email, domain)
            rows.append(_Row(
                company=person.company or domain,
                name=person.name,
                title=person.title,
                email=person.email,
                subject=subject,
                html=html,
                person=person,
            ))

    report["people_found"] = len(rows)

    if not rows:
        log.warning("No verified contacts found")
        console.print("[yellow]No verified contacts found. Nothing to send.")
        _write_report({**report, "status": "no_contacts"})
        return

    # ── Stage 3: summary table ────────────────────────────────────────────────
    console.rule("[bold cyan]Stage 3 — Summary")
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Company", style="cyan")
    table.add_column("Name")
    table.add_column("Title")
    table.add_column("Email")
    table.add_column("Subject")

    for row in rows:
        display_email = row.email if send_real else config.DEMO_RECIPIENT
        table.add_row(row.company, row.name, row.title, display_email, row.subject)

    console.print(table)

    if dry_run:
        log.info("Dry run complete — %d email(s) would be sent", len(rows))
        console.print("\n[bold yellow]--dry-run: no emails sent.[/bold yellow]")
        _write_report({**report, "status": "dry_run"})
        return

    # ── Gate ──────────────────────────────────────────────────────────────────
    target_label = "real prospects" if send_real else f"DEMO_RECIPIENT ({config.DEMO_RECIPIENT})"
    answer = console.input(
        f"\n[bold]Send {len(rows)} email(s) to {target_label}? [y/N][/bold] "
    ).strip().lower()

    if answer != "y":
        log.info("User aborted at gate")
        console.print("[yellow]Aborted. Nothing sent.")
        _write_report({**report, "status": "aborted"})
        return

    # ── Stage 4: send ─────────────────────────────────────────────────────────
    console.rule("[bold cyan]Stage 4 — Sending")
    sent = 0
    sent_to: list[str] = []
    for row in rows:
        recipient_email = row.email if send_real else config.DEMO_RECIPIENT
        recipient_name = row.name if send_real else "Demo"
        try:
            result = brevo.send(recipient_email, recipient_name, row.subject, row.html)
            log.info("Sent to %s — %s", recipient_email, result)
            console.print(f"  [green]Sent to {recipient_email} — {result}")
            sent += 1
            sent_to.append(recipient_email)
        except Exception as exc:
            log.error("Failed to send to %s: %s", recipient_email, exc)
            console.print(f"  [red]Failed to send to {recipient_email}: {exc}")

    report["emails_sent"] = sent
    report["sent_to"] = sent_to
    _write_report({**report, "status": "done"})
    console.print(f"\n[bold green]Done — {sent}/{len(rows)} emails sent.[/bold green]")


def _setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def _write_report(data: dict) -> None:
    RUNS_DIR.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = RUNS_DIR / f"run_{ts}.json"
    path.write_text(json.dumps(data, indent=2))
    log.info("Run report saved -> %s", path)
    console.print(f"  [dim]Report saved -> {path}[/dim]")
