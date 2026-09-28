from __future__ import annotations

import argparse
from datetime import date, datetime
from pathlib import Path

from csp_trainer.config import AppConfig, ConfigurationError, load_config
from csp_trainer.mailer import send_pdf_email
from csp_trainer.pdf_generator import generate_daily_pdf
from csp_trainer.question_provider import StaticQuestionProvider


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a daily CSP training PDF and optionally send it by email."
    )
    parser.add_argument(
        "--config",
        default="config.ini",
        help="Path to config file. Defaults to config.ini.",
    )
    parser.add_argument(
        "--date",
        help="Training date in YYYY-MM-DD format. Defaults to today.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Generate the PDF but do not send email.",
    )
    parser.add_argument(
        "--no-email",
        action="store_true",
        help="Generate the PDF and skip email even when email.enabled is true.",
    )
    parser.add_argument(
        "--require-email",
        action="store_true",
        help="Fail if the email is not sent. Intended for daily scheduled runs.",
    )
    return parser.parse_args()


def parse_training_date(value: str | None) -> date:
    if value is None:
        return date.today()
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise SystemExit("--date must use YYYY-MM-DD format.") from exc


def build_output_path(config: AppConfig, training_date: date) -> Path:
    output_dir = config.project_root / config.paths.output_dir
    filename = f"{config.paths.filename_prefix}_{training_date.isoformat()}.pdf"
    return output_dir / filename


def main() -> int:
    args = parse_args()
    training_date = parse_training_date(args.date)

    try:
        config = load_config(args.config)
    except ConfigurationError as exc:
        print(f"[config] {exc}")
        return 2

    provider = StaticQuestionProvider(
        questions_file=config.project_root / config.paths.questions_file
    )
    questions = provider.get_daily_questions(training_date)

    output_path = build_output_path(config, training_date)
    generate_daily_pdf(
        questions=questions,
        output_path=output_path,
        training_date=training_date,
        title=config.app.title,
    )

    print(f"[pdf] Generated: {output_path}")

    skip_requested = args.dry_run or args.no_email
    if args.require_email and skip_requested:
        print("[email] --require-email cannot be used with --dry-run or --no-email.")
        return 2

    if args.require_email and not config.email.enabled:
        print("[email] Email is required for this run, but email.enabled is false.")
        print("[email] Run scripts/setup_email.ps1 first, then try again.")
        return 2

    should_send = config.email.enabled and not skip_requested
    if should_send:
        try:
            send_pdf_email(
                email_config=config.email,
                pdf_path=output_path,
                training_date=training_date,
                title=config.app.title,
            )
        except Exception as exc:
            print(f"[email] Send failed: {exc}")
            return 1
        print("[email] Sent successfully.")
    else:
        reason = "dry-run/no-email" if args.dry_run or args.no_email else "email.disabled"
        print(f"[email] Skipped ({reason}).")
        if args.require_email:
            return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

