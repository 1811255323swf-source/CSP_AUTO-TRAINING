from __future__ import annotations

import smtplib
from datetime import date
from email.message import EmailMessage
from pathlib import Path

from csp_trainer.config import EmailSection


def _build_message(
    email_config: EmailSection,
    pdf_path: Path,
    training_date: date,
    title: str,
) -> EmailMessage:
    message = EmailMessage()
    message["Subject"] = f"{email_config.subject_prefix} {training_date.isoformat()}"
    message["From"] = email_config.from_addr
    message["To"] = ", ".join(email_config.to_addrs)
    message.set_content(
        "\n".join(
            [
                f"{title} 已生成。",
                "",
                f"训练日期：{training_date.isoformat()}",
                "附件中包含今天的 3 道 CSP 风格 C++ 训练题。",
                "",
                "祝你今天训练顺利。",
            ]
        )
    )

    data = pdf_path.read_bytes()
    message.add_attachment(
        data,
        maintype="application",
        subtype="pdf",
        filename=pdf_path.name,
    )
    return message


def send_pdf_email(
    email_config: EmailSection,
    pdf_path: Path,
    training_date: date,
    title: str,
) -> None:
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF does not exist: {pdf_path}")

    missing = []
    if not email_config.smtp_host:
        missing.append("email.smtp_host")
    if not email_config.username:
        missing.append("email.username")
    if not email_config.from_addr:
        missing.append("email.from_addr")
    if not email_config.to_addrs:
        missing.append("email.to_addrs")

    password = email_config.password
    if not password:
        missing.append(f"environment variable {email_config.password_env}")

    if missing:
        raise RuntimeError("Missing email configuration: " + ", ".join(missing))

    message = _build_message(email_config, pdf_path, training_date, title)

    if email_config.use_ssl:
        with smtplib.SMTP_SSL(email_config.smtp_host, email_config.smtp_port) as server:
            server.login(email_config.username, password)
            server.send_message(message)
        return

    with smtplib.SMTP(email_config.smtp_host, email_config.smtp_port) as server:
        if email_config.use_starttls:
            server.starttls()
        server.login(email_config.username, password)
        server.send_message(message)

