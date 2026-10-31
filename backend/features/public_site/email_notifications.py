"""Email notification for public website leads."""

import logging
import os
from email.utils import parseaddr


LOGGER = logging.getLogger(__name__)
TRUE_VALUES = frozenset(("1", "true", "yes", "on"))


def _env_bool(environ, name, default=False):
    raw = environ.get(name)
    if raw is None:
        return default
    return str(raw).strip().lower() in TRUE_VALUES


def _valid_email(value):
    raw = str(value or "").strip()
    _name, address = parseaddr(raw)
    return bool(address and "@" in address and "\r" not in raw and "\n" not in raw)


class LeadEmailNotifier:
    def __init__(self, environ=None, *, get_db=None, send_email=None):
        self.environ = os.environ if environ is None else environ
        self.get_db = get_db
        self.send_email = send_email

    def readiness(self):
        env = self.environ
        enabled = _env_bool(env, "PUBLIC_SITE_LEAD_EMAIL_ENABLED")
        recipient = str(env.get("PUBLIC_SITE_LEAD_EMAIL_TO", "") or "").strip()
        issues = []
        if not enabled:
            issues.append("notification_disabled")
        if not _valid_email(recipient):
            issues.append("recipient_missing_or_invalid")
        if not str(env.get("SMTP_HOST", "") or "").strip():
            issues.append("smtp_host_missing")
        try:
            port = int(env.get("SMTP_PORT", "465"))
            if not 1 <= port <= 65535:
                raise ValueError
        except (TypeError, ValueError):
            port = None
            issues.append("smtp_port_invalid")
        # The shared _send_email helper requires SMTP_FROM; do not report the
        # notifier as ready when the transport will reject the message.
        sender = str(env.get("SMTP_FROM", "") or "").strip()
        if not _valid_email(sender):
            issues.append("smtp_sender_missing_or_invalid")
        smtp_user = str(env.get("SMTP_USER", "") or "").strip()
        smtp_password = str(env.get("SMTP_PASSWORD", "") or "")
        if bool(smtp_user) != bool(smtp_password):
            issues.append("smtp_credentials_incomplete")
        use_ssl = _env_bool(env, "SMTP_SSL", default=True)
        use_tls = _env_bool(env, "SMTP_TLS", default=not use_ssl)
        transport = (
            ("SMTP over SSL" if use_ssl else ("SMTP with STARTTLS" if use_tls else "SMTP"))
            + (f", port {port}" if port else "")
        )
        return {
            "enabled": enabled,
            "configured": not issues,
            "issues": issues,
            "recipient": recipient if _valid_email(recipient) else None,
            "transport": transport,
            "deliveryVerified": False,
        }

    def notify(self, company_id, lead_id):
        state = self.readiness()
        if not state["enabled"]:
            return False
        if not state["configured"] or not self.get_db or not self.send_email:
            LOGGER.warning(
                "public_site_lead_email_skipped lead_id=%s reason=configuration_incomplete",
                lead_id,
            )
            return False

        conn = None
        cur = None
        try:
            conn = self.get_db()
            cur = conn.cursor()
            cur.execute(
                """SELECT id,name,phone,email,source,lead_type,created_at
                     FROM crm_leads
                    WHERE id=%s AND company_id=%s AND created_by='Сайт'""",
                (lead_id, company_id),
            )
            row = cur.fetchone()
            if not row:
                LOGGER.warning(
                    "public_site_lead_email_skipped lead_id=%s reason=lead_not_found",
                    lead_id,
                )
                return False
            lead = dict(row) if hasattr(row, "keys") else dict(
                zip(("id", "name", "phone", "email", "source", "lead_type", "created_at"), row)
            )
            body = "\n".join((
                "Поступила новая заявка с сайта СтройКа.",
                "",
                f"Номер: {lead.get('id')}",
                f"Тип: {lead.get('lead_type') or 'Клиент'}",
                f"Имя: {lead.get('name') or 'не указано'}",
                f"Телефон: {lead.get('phone') or 'не указан'}",
                f"Email: {lead.get('email') or 'не указан'}",
                f"Источник: {lead.get('source') or 'Сайт'}",
                "",
                "Откройте кабинет СтройКа и найдите заявку по её номеру.",
                "https://stroyka26.pro/",
            ))
            sent = bool(self.send_email(
                state["recipient"],
                f"Новая заявка с сайта №{lead.get('id')}",
                body,
            ))
            LOGGER.info(
                "public_site_lead_email_%s lead_id=%s",
                "sent" if sent else "failed",
                lead_id,
            )
            return sent
        except Exception:
            LOGGER.warning(
                "public_site_lead_email_failed lead_id=%s reason=notification_error",
                lead_id,
            )
            return False
        finally:
            if cur is not None:
                try:
                    cur.close()
                except Exception:
                    pass
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass


if __name__ == "__main__":
    import json

    print(json.dumps(LeadEmailNotifier().readiness(), ensure_ascii=False, indent=2))
