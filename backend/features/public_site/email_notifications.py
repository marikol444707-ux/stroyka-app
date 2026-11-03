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
        sender = str(env.get("SMTP_FROM", "") or env.get("SMTP_USER", "") or "").strip()
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

    def enqueue(self, cursor, company_id, lead_id):
        """Persist a notification in the same transaction as the CRM lead."""
        if not _env_bool(self.environ, "PUBLIC_SITE_LEAD_EMAIL_ENABLED"):
            return False
        cursor.execute(
            """INSERT INTO public_site_lead_email_outbox (company_id, lead_id)
               VALUES (%s, %s)
               ON CONFLICT (company_id, lead_id) DO NOTHING""",
            (int(company_id), int(lead_id)),
        )
        return True

    def dispatch_pending(self, limit=20):
        """Deliver due messages and leave failures queued for automatic retry."""
        state = self.readiness()
        if not state["enabled"]:
            return {"processed": 0, "sent": 0, "retrying": 0, "paused": "disabled"}
        if not state["configured"] or not self.get_db or not self.send_email:
            LOGGER.warning(
                "public_site_lead_email_queue_paused issues=%s",
                ",".join(state["issues"] or ["delivery_unavailable"]),
            )
            return {"processed": 0, "sent": 0, "retrying": 0, "paused": "configuration_incomplete"}

        conn = self.get_db()
        cur = conn.cursor()
        try:
            cur.execute(
                """WITH due AS (
                       SELECT id
                         FROM public_site_lead_email_outbox
                        WHERE (status='pending' AND next_attempt_at <= NOW())
                           OR (status='sending' AND locked_at < NOW() - INTERVAL '10 minutes')
                        ORDER BY next_attempt_at, id
                        LIMIT %s
                        FOR UPDATE SKIP LOCKED
                   )
                   UPDATE public_site_lead_email_outbox AS outbox
                      SET status='sending',
                          attempts=outbox.attempts + 1,
                          locked_at=NOW(),
                          updated_at=NOW()
                     FROM due
                    WHERE outbox.id=due.id
                   RETURNING outbox.id, outbox.company_id, outbox.lead_id, outbox.attempts""",
                (max(1, min(int(limit), 100)),),
            )
            rows = cur.fetchall()
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()
            conn.close()

        sent_count = 0
        retry_count = 0
        for row in rows:
            outbox_id, company_id, lead_id, attempts = row
            sent = self.notify(company_id, lead_id)
            update_conn = self.get_db()
            update_cur = update_conn.cursor()
            try:
                if sent:
                    update_cur.execute(
                        """UPDATE public_site_lead_email_outbox
                              SET status='sent', sent_at=NOW(), locked_at=NULL,
                                  last_error=NULL, updated_at=NOW()
                            WHERE id=%s""",
                        (outbox_id,),
                    )
                    sent_count += 1
                else:
                    retry_seconds = min(21600, 60 * (2 ** min(max(int(attempts) - 1, 0), 9)))
                    update_cur.execute(
                        """UPDATE public_site_lead_email_outbox
                              SET status='pending',
                                  next_attempt_at=NOW() + (%s * INTERVAL '1 second'),
                                  locked_at=NULL,
                                  last_error='delivery_failed_or_lead_unavailable',
                                  updated_at=NOW()
                            WHERE id=%s""",
                        (retry_seconds, outbox_id),
                    )
                    retry_count += 1
                update_conn.commit()
            except Exception:
                update_conn.rollback()
                raise
            finally:
                update_cur.close()
                update_conn.close()

        return {
            "processed": len(rows),
            "sent": sent_count,
            "retrying": retry_count,
            "paused": None,
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
