"""Orchestrate all stages: lookalikes -> people -> emails -> gate -> send."""
from __future__ import annotations
from dataclasses import dataclass

from rich.console import Console
from rich.table import Table

import config
import emails
from stages import ocean, brevo
from stages import hunter
from stages.prospeo import Person

console = Console()


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
    config.load()

    # ── Stage 1: lookalikes ───────────────────────────────────────────────────
    console.rule("[bold cyan]Stage 1 — Lookalikes")
    try:
        domains = ocean.find_lookalikes(seed_domain)
    except Exception as exc:
        console.print(f"[red]Ocean stage failed: {exc}")
        return

    domains = domains[:limit_companies]
    if not domains:
        console.print("[yellow]No lookalike companies found. Exiting.")
        return
    console.print(f"  Found {len(domains)} companies: {domains}")

    # ── Stage 2: people + email resolve ──────────────────────────────────────
    console.rule("[bold cyan]Stage 2 — People")
    rows: list[_Row] = []
    seen_emails: set[str] = set()

    for domain in domains:
        try:
            people = hunter.find_people(domain)
        except Exception as exc:
            console.print(f"  [red]Skipping {domain}: {exc}")
            continue

        for person in people:
            if not person.email or person.email in seen_emails:
                continue
            seen_emails.add(person.email)
            try:
                subject, html = emails.build(person, seed_domain)
            except Exception as exc:
                console.print(f"  [red]Email build failed for {person.name}: {exc}")
                continue
            rows.append(_Row(
                company=person.company or domain,
                name=person.name,
                title=person.title,
                email=person.email,
                subject=subject,
                html=html,
                person=person,
            ))

    if not rows:
        console.print("[yellow]No verified contacts found. Nothing to send.")
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
        console.print("\n[bold yellow]--dry-run: no emails sent.[/bold yellow]")
        return

    # ── Gate ──────────────────────────────────────────────────────────────────
    target_label = "real prospects" if send_real else f"DEMO_RECIPIENT ({config.DEMO_RECIPIENT})"
    answer = console.input(
        f"\n[bold]Send {len(rows)} email(s) to {target_label}? [y/N][/bold] "
    ).strip().lower()

    if answer != "y":
        console.print("[yellow]Aborted. Nothing sent.")
        return

    # ── Stage 4: send ─────────────────────────────────────────────────────────
    console.rule("[bold cyan]Stage 4 — Sending")
    sent = 0
    for row in rows:
        recipient_email = row.email if send_real else config.DEMO_RECIPIENT
        recipient_name = row.name if send_real else "Demo"
        try:
            result = brevo.send(recipient_email, recipient_name, row.subject, row.html)
            console.print(f"  [green]Sent to {recipient_email} — {result}")
            sent += 1
        except Exception as exc:
            console.print(f"  [red]Failed to send to {recipient_email}: {exc}")

    console.print(f"\n[bold green]Done — {sent}/{len(rows)} emails sent.[/bold green]")
