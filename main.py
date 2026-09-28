from __future__ import annotations

import argparse
from datetime import date, datetime
from pathlib import Path

from csp_trainer.ai_question_provider import AIQuestionProvider
from csp_trainer.config import AppConfig, ConfigurationError, load_config
from csp_trainer.mailer import send_pdf_email
from csp_trainer.pdf_generator import generate_daily_pdf
from csp_trainer.question_provider import QuestionProvider, StaticQuestionProvider


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
    parser.add_argument(
        "--allow-static-fallback",
        action="store_true",
        help="When the AI provider fails, fall back to the local question bank "
        "instead of aborting the run.",
    )
    return parser.parse_args()


def parse_training_date(value: str | None) -> date:
    if value is None:
        return date.today()
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise SystemExit("--date must use YYYY-MM-DD format.") from exc


def static_provider(config: AppConfig) -> StaticQuestionProvider:
    return StaticQuestionProvider(
        questions_file=config.project_root / config.paths.questions_file
    )


def build_provider(config: AppConfig, args: argparse.Namespace) -> tuple[QuestionProvider, bool]:
    """Pick the question source declared in config. Returns (provider, used_fallback)."""
    if config.app.provider != "ai":
        return static_provider(config), False

    try:
        return AIQuestionProvider(config=config.ai), False
    except ConfigurationError as exc:
        if not args.allow_static_fallback or not config.ai.fallback_to_static:
            raise
        print(f"[ai] {exc}")
        print("[ai] Falling back to the static question bank.")
        return static_provider(config), True


def resolve_questions(
    provider: QuestionProvider,
    config: AppConfig,
    training_date: date,
    args: argparse.Namespace,
) -> tuple[list, bool]:
    """Return (questions, used_fallback)."""
    try:
        return provider.get_daily_questions(training_date), False
    except Exception as exc:
        if not isinstance(provider, AIQuestionProvider):
            raise
        if not args.allow_static_fallback or not config.ai.fallback_to_static:
            raise
        print(f"[ai] Generation failed: {exc}")
        print("[ai] Falling back to the static question bank.")
        return static_provider(config).get_daily_questions(training_date), True


def build_output_path(config: AppConfig, training_date: date, source: str = "static") -> Path:
    output_dir = config.project_root / config.paths.output_dir
    suffix = "_AI" if source == "ai" else ""
    filename = f"{config.paths.filename_prefix}_{training_date.isoformat()}{suffix}.pdf"
    return output_dir / filename


def main() -> int:
    args = parse_args()
    training_date = parse_training_date(args.date)

    try:
        config = load_config(args.config)
    except ConfigurationError as exc:
        print(f"[config] {exc}")
        return 2

    try:
        provider, used_fallback = build_provider(config, args)
        questions, fell_back = resolve_questions(provider, config, training_date, args)
        used_fallback = used_fallback or fell_back
    except ConfigurationError as exc:
        print(f"[config] {exc}")
        return 2
    except Exception as exc:
        print(f"[questions] Failed to build today's question set: {exc}")
        return 1

    if used_fallback:
        source = "static"
        source_label = "本地题库（AI 出题失败后回退）"
    elif config.app.provider == "ai":
        source = "ai"
        source_label = f"AI 生成（{config.ai.model}）"
    else:
        source = "static"
        source_label = "本地题库"

    print(f"[questions] Source: {source} ({len(questions)} questions).")

    try:
        output_path = build_output_path(config, training_date, source)
        generate_daily_pdf(
            questions=questions,
            output_path=output_path,
            training_date=training_date,
            title=config.app.title,
            source_label=source_label,
        )
    except Exception as exc:
        print(f"[pdf] Generation failed: {exc}")
        return 1

    print(f"[pdf] Generated: {output_path}")

    skip_requested = args.dry_run or args.no_email
    if args.require_email and skip_requested:
        print("[email] --require-email cannot be used with --dry-run or --no-email.")
        return 2

    if args.require_email and not config.email.enabled:
        print("[email] Email is required for this run, but email.enabled is false.")
        return 2

    should_send = config.email.enabled and not skip_requested
    if should_send:
        try:
            send_pdf_email(
                email_config=config.email,
                pdf_path=output_path,
                training_date=training_date,
                title=config.app.title,
                source_label=source_label,
                source=source,
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

