from __future__ import annotations

import configparser
import os
from dataclasses import dataclass
from pathlib import Path


class ConfigurationError(RuntimeError):
    """Raised when the local configuration is missing or invalid."""


VALID_PROVIDERS = ("static", "ai")


@dataclass(frozen=True)
class AppSection:
    title: str
    provider: str


@dataclass(frozen=True)
class AISection:
    api_key_env: str
    base_url: str
    model: str
    timeout: float
    max_retries: int
    temperature: float
    fallback_to_static: bool

    @property
    def api_key(self) -> str | None:
        value = os.getenv(self.api_key_env, "")
        return value.strip() or None


@dataclass(frozen=True)
class PathsSection:
    questions_file: Path
    output_dir: Path
    filename_prefix: str


@dataclass(frozen=True)
class EmailSection:
    enabled: bool
    smtp_host: str
    smtp_port: int
    use_ssl: bool
    use_starttls: bool
    username: str
    password_env: str
    from_addr: str
    to_addrs: tuple[str, ...]
    subject_prefix: str

    @property
    def password(self) -> str | None:
        return os.getenv(self.password_env)


@dataclass(frozen=True)
class AppConfig:
    project_root: Path
    app: AppSection
    paths: PathsSection
    email: EmailSection
    ai: AISection


def _get_bool(
    parser: configparser.ConfigParser,
    section: str,
    option: str,
    fallback: bool,
) -> bool:
    if not parser.has_option(section, option):
        return fallback
    return parser.getboolean(section, option)


def _split_addresses(value: str) -> tuple[str, ...]:
    if not value.strip():
        return ()
    addresses = tuple(addr.strip() for addr in value.split(",") if addr.strip())
    return addresses


def _env_override(name: str, current: str) -> str:
    value = os.getenv(name)
    return value if value is not None and value.strip() else current


def load_config(config_path: str | Path) -> AppConfig:
    path = Path(config_path)
    if not path.is_absolute():
        path = Path.cwd() / path
    path = path.resolve()

    if not path.exists():
        raise ConfigurationError(
            f"Config file not found: {path}. Copy config.example.ini to config.ini first."
        )

    parser = configparser.ConfigParser()
    parser.read(path, encoding="utf-8-sig")

    project_root = path.parent

    app = AppSection(
        title=parser.get("app", "title", fallback="CSP 每日三题训练"),
        provider=parser.get("app", "provider", fallback="static"),
    )
    if app.provider not in VALID_PROVIDERS:
        raise ConfigurationError(
            f"app.provider must be one of {', '.join(VALID_PROVIDERS)}, got '{app.provider}'."
        )

    paths = PathsSection(
        questions_file=Path(parser.get("paths", "questions_file", fallback="data/questions.json")),
        output_dir=Path(parser.get("paths", "output_dir", fallback="output")),
        filename_prefix=parser.get("paths", "filename_prefix", fallback="CSP训练"),
    )

    smtp_port_raw = _env_override(
        "CSP_SMTP_PORT",
        parser.get("email", "smtp_port", fallback="465"),
    )
    try:
        smtp_port = int(smtp_port_raw)
    except ValueError as exc:
        raise ConfigurationError("email.smtp_port must be an integer.") from exc

    email_enabled = _get_bool(parser, "email", "enabled", fallback=False)

    email = EmailSection(
        enabled=email_enabled,
        smtp_host=_env_override(
            "CSP_SMTP_HOST",
            parser.get("email", "smtp_host", fallback="smtp.qq.com"),
        ),
        smtp_port=smtp_port,
        use_ssl=_get_bool(parser, "email", "use_ssl", fallback=True),
        use_starttls=_get_bool(parser, "email", "use_starttls", fallback=False),
        username=_env_override(
            "CSP_SMTP_USER",
            parser.get("email", "username", fallback=""),
        ),
        password_env=parser.get("email", "password_env", fallback="CSP_SMTP_PASSWORD"),
        from_addr=_env_override(
            "CSP_MAIL_FROM",
            parser.get("email", "from_addr", fallback=""),
        ),
        to_addrs=_split_addresses(
            _env_override(
                "CSP_MAIL_TO",
                parser.get("email", "to_addrs", fallback=""),
            )
        ),
        subject_prefix=_env_override(
            "CSP_SUBJECT_PREFIX",
            parser.get("email", "subject_prefix", fallback="CSP 每日训练"),
        ),
    )

    if email.use_ssl and email.use_starttls:
        raise ConfigurationError("email.use_ssl and email.use_starttls cannot both be true.")

    ai_timeout_raw = _env_override(
        "CSP_AI_TIMEOUT",
        parser.get("ai", "timeout", fallback="60"),
    )
    ai_retries_raw = _env_override(
        "CSP_AI_MAX_RETRIES",
        parser.get("ai", "max_retries", fallback="2"),
    )
    ai_temperature_raw = _env_override(
        "CSP_AI_TEMPERATURE",
        parser.get("ai", "temperature", fallback="1.0"),
    )
    try:
        ai_timeout = float(ai_timeout_raw)
        ai_retries = int(ai_retries_raw)
        ai_temperature = float(ai_temperature_raw)
    except ValueError as exc:
        raise ConfigurationError(
            "ai.timeout / ai.max_retries / ai.temperature must be numeric."
        ) from exc

    if ai_timeout <= 0:
        raise ConfigurationError("ai.timeout must be greater than 0.")
    if ai_retries < 0:
        raise ConfigurationError("ai.max_retries cannot be negative.")
    if not 0.0 <= ai_temperature <= 2.0:
        raise ConfigurationError("ai.temperature must be between 0.0 and 2.0.")

    ai = AISection(
        api_key_env=parser.get("ai", "api_key_env", fallback="DEEPSEEK_API_KEY"),
        base_url=_env_override(
            "CSP_AI_BASE_URL",
            parser.get("ai", "base_url", fallback="https://api.deepseek.com"),
        ),
        model=_env_override(
            "CSP_AI_MODEL",
            parser.get("ai", "model", fallback="deepseek-chat"),
        ),
        timeout=ai_timeout,
        max_retries=ai_retries,
        temperature=ai_temperature,
        fallback_to_static=_get_bool(parser, "ai", "fallback_to_static", fallback=False),
    )

    return AppConfig(
        project_root=project_root, app=app, paths=paths, email=email, ai=ai
    )

