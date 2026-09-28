from __future__ import annotations

import configparser
import os
from dataclasses import dataclass
from pathlib import Path


class ConfigurationError(RuntimeError):
    """Raised when the local configuration is missing or invalid."""


@dataclass(frozen=True)
class AppSection:
    title: str
    provider: str


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
    if app.provider != "static":
        raise ConfigurationError(
            "Only provider=static is implemented in this stable first version."
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
        subject_prefix=parser.get("email", "subject_prefix", fallback="CSP 每日训练"),
    )

    if email.use_ssl and email.use_starttls:
        raise ConfigurationError("email.use_ssl and email.use_starttls cannot both be true.")

    return AppConfig(project_root=project_root, app=app, paths=paths, email=email)

