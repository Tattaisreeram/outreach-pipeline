"""CLI entrypoint: python main.py <seed_domain> [--dry-run] [--send-real]"""
import argparse
import pipeline


def main() -> None:
    parser = argparse.ArgumentParser(description="Outreach pipeline")
    parser.add_argument("seed_domain", help="Domain to find lookalikes for")
    parser.add_argument("--dry-run", action="store_true", help="Skip sending emails")
    parser.add_argument("--send-real", action="store_true", help="Send to real prospects (default: DEMO_RECIPIENT)")
    parser.add_argument("--limit-companies", type=int, default=3)
    args = parser.parse_args()

    pipeline.run(
        seed_domain=args.seed_domain,
        dry_run=args.dry_run,
        send_real=args.send_real,
        limit_companies=args.limit_companies,
    )


if __name__ == "__main__":
    main()
