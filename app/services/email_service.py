import logging
import re
from email.message import EmailMessage

import aiosmtplib
from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.config import get_settings

logger = logging.getLogger(__name__)
_HEADER_BREAKS = re.compile(r"[\r\n]+")
_templates = Environment(
    loader=FileSystemLoader("app/templates/emails"),
    autoescape=select_autoescape(("html", "xml")),
)


def _header_value(value: str) -> str:
    return _HEADER_BREAKS.sub(" ", value).strip()


def _safe_subject(title: str) -> str:
    return _header_value(f"Candidature reçue - {title}")[:200]


def _message(
    recipient: str,
    subject: str,
    template_context: dict[str, str],
    template_stem: str,
) -> EmailMessage:
    message = EmailMessage()
    message["To"] = _header_value(recipient)
    message["From"] = _header_value(get_settings().admin_notification_email)
    message["Subject"] = _safe_subject(subject)
    text_template = _templates.get_template(f"{template_stem}.txt")
    html_template = _templates.get_template(f"{template_stem}.html")
    message.set_content(text_template.render(**template_context))
    message.add_alternative(html_template.render(**template_context), subtype="html")
    return message


async def _send(message: EmailMessage) -> bool:
    settings = get_settings()
    if not settings.smtp_host.strip():
        logger.info("Email désactivé : SMTP_HOST est vide.")
        return False
    try:
        await aiosmtplib.send(
            message,
            hostname=settings.smtp_host,
            port=settings.smtp_port,
            username=settings.smtp_user or None,
            password=settings.smtp_password or None,
            start_tls=settings.smtp_starttls,
        )
    except Exception:
        logger.exception("Échec d'envoi email ; la candidature reste conservée.")
        return False
    return True


async def send_application_notifications(
    candidate_email: str,
    candidate_name: str,
    job_title: str,
    applied_at: str,
) -> None:
    context = {
        "candidate_name": _header_value(candidate_name),
        "job_title": _header_value(job_title),
        "applied_at": _header_value(applied_at),
    }
    subject = job_title
    candidate_message = _message(
        candidate_email, subject, context, "application_confirmation_candidate"
    )
    admin_email = get_settings().admin_notification_email
    admin_message = _message(admin_email, subject, context, "application_confirmation_admin")
    await _send(candidate_message)
    await _send(admin_message)
