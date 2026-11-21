"""Queue a Russian owner alert when a new external CRM lead is stored.

Delivery uses messenger_outbox. The existing MAX dispatcher sends both Max and
Telegram rows about once a minute, so creating the lead never waits on a bot.
"""

import json
import logging
import os
import urllib.error
import urllib.request

LOGGER = logging.getLogger(__name__)
EVENT_TYPE = "crm_lead_created"
NOTIFY_SAVEPOINT = "crm_lead_notify"
DISPATCH_SAVEPOINT = "crm_lead_telegram_dispatch"
MAX_ATTEMPTS = 5


def _environ(environ):
    return os.environ if environ is None else environ


def _chat_id(value) -> str:
    raw = str(value or "").strip()
    if not raw or any(char.isspace() for char in raw) or len(raw) > 120:
        return ""
    return raw


def _company_id(value):
    try:
        company_id = int(value)
    except (TypeError, ValueError):
        return None
    return company_id if company_id > 0 else None


def notification_targets(environ=None):
    env = _environ(environ)
    telegram = _chat_id(env.get("LEAD_NOTIFY_TELEGRAM_CHAT_ID"))
    max_chat = _chat_id(env.get("LEAD_NOTIFY_MAX_CHAT_ID"))
    allowed_company = _company_id(env.get("LEAD_NOTIFY_COMPANY_ID"))
    return telegram, max_chat, allowed_company


def public_app_url(environ=None) -> str:
    raw = str(_environ(environ).get("APP_PUBLIC_URL") or "https://stroyka26.pro").strip().rstrip("/")
    if not raw.startswith("https://") or " " in raw:
        return "https://stroyka26.pro"
    return raw


def lead_crm_link(lead_id, public_url) -> str:
    return f"{str(public_url or 'https://stroyka26.pro').rstrip('/')}/app?page=crm&lead={int(lead_id)}"


def lead_notification_parts(*, lead_id, name, phone, work_type, address, source, public_url) -> tuple[str, str, str]:
    link = lead_crm_link(lead_id, public_url)
    body = "\n".join((
        f"Имя: {name or 'не указано'}",
        f"Телефон: {phone or 'не указан'}",
        f"Что нужно: {work_type or 'не указано'}",
        f"Адрес: {address or 'не указан'}",
        f"Источник: {source or 'не указан'}",
        f"CRM: {link}",
    ))
    return "Новая заявка", body, link


def enqueue_lead_owner_notification(
    cursor,
    *,
    company_id,
    lead_id,
    name="",
    phone="",
    work_type="",
    address="",
    source="",
    environ=None,
):
    """Insert owner alerts in the current transaction. Never raises."""
    owner_company_id = _company_id(company_id)
    lead_number = _company_id(lead_id)
    if cursor is None or not owner_company_id or not lead_number:
        return False
    telegram, max_chat, allowed_company = notification_targets(environ)
    if not telegram and not max_chat:
        return False
    if allowed_company and allowed_company != owner_company_id:
        return False
    title, body, link = lead_notification_parts(
        lead_id=lead_number,
        name=str(name or "")[:255],
        phone=str(phone or "")[:80],
        work_type=str(work_type or "")[:255],
        address=str(address or "")[:500],
        source=str(source or "")[:255],
        public_url=public_app_url(environ),
    )
    channels = []
    if telegram:
        channels.append(("telegram", telegram))
    if max_chat:
        channels.append(("max", max_chat))
    try:
        cursor.execute(f"SAVEPOINT {NOTIFY_SAVEPOINT}")
        for provider, chat_id in channels:
            cursor.execute(
                """
                INSERT INTO messenger_outbox
                    (owner_scope,company_id,project_id,provider,external_user_id,chat_id,
                     event_type,entity_type,entity_id,title,body,payload_json,actions_json,
                     status,priority)
                VALUES
                    ('company',%s,NULL,%s,'',%s,%s,'crm_lead',%s,%s,%s,%s::jsonb,%s::jsonb,'queued',1)
                """,
                (
                    owner_company_id,
                    provider,
                    chat_id,
                    EVENT_TYPE,
                    lead_number,
                    title,
                    body,
                    json.dumps(
                        {"leadId": lead_number, "companyId": owner_company_id},
                        ensure_ascii=False,
                    ),
                    json.dumps(
                        [{"label": "Открыть CRM", "url": link}],
                        ensure_ascii=False,
                    ),
                ),
            )
        cursor.execute(f"RELEASE SAVEPOINT {NOTIFY_SAVEPOINT}")
        return True
    except Exception:
        LOGGER.warning(
            "lead_owner_notify_enqueue_failed company_id=%s lead_id=%s",
            owner_company_id,
            lead_number,
        )
        try:
            cursor.execute(f"ROLLBACK TO SAVEPOINT {NOTIFY_SAVEPOINT}")
        except Exception:
            LOGGER.warning(
                "lead_owner_notify_savepoint_failed company_id=%s lead_id=%s",
                owner_company_id,
                lead_number,
            )
        return False


def _row_value(row, key, index, default=""):
    if isinstance(row, dict):
        return row.get(key, default)
    try:
        return row[index]
    except Exception:
        return default


def send_telegram_lead_message(chat_id, text, *, token=None, opener=None):
    bot_token = token if token is not None else str(os.environ.get("TELEGRAM_BOT_API_TOKEN") or "").strip()
    if not bot_token:
        raise RuntimeError("telegram_bot_token_missing")
    url = "https://api.telegram.org/bot" + bot_token + "/sendMessage"
    payload = json.dumps(
        {"chat_id": chat_id, "text": text[:4000], "disable_web_page_preview": True},
        ensure_ascii=False,
    ).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=payload,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    open_url = opener or urllib.request.urlopen
    try:
        with open_url(request, timeout=20) as response:
            raw = response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        exc.read()
        raise RuntimeError("telegram_delivery_failed") from None
    except Exception:
        raise RuntimeError("telegram_delivery_failed") from None
    try:
        data = json.loads(raw or "{}")
    except json.JSONDecodeError:
        raise RuntimeError("telegram_delivery_failed") from None
    if not isinstance(data, dict) or not data.get("ok"):
        raise RuntimeError("telegram_delivery_failed")
    result = data.get("result") if isinstance(data.get("result"), dict) else {}
    return str(result.get("message_id") or "")


def dispatch_telegram_lead_outbox(cursor, *, send_message, dry_run=False, limit=20):
    """Send queued Telegram lead alerts. Failures stay in the outbox and never raise."""
    outcome = {"planned": [], "sent": [], "failed": []}
    if cursor is None or send_message is None:
        return outcome
    bounded = max(1, min(int(limit or 20), 100))
    lock = "" if dry_run else " FOR UPDATE SKIP LOCKED"
    try:
        cursor.execute(f"SAVEPOINT {DISPATCH_SAVEPOINT}")
        cursor.execute(
            f"""
            SELECT id, company_id, chat_id, title, body, attempts
              FROM messenger_outbox
             WHERE provider='telegram'
               AND event_type=%s
               AND owner_scope='company'
               AND company_id IS NOT NULL
               AND status='queued'
               AND (next_attempt_at IS NULL OR next_attempt_at <= NOW())
             ORDER BY priority ASC, id ASC
             LIMIT %s
             {lock}
            """,
            (EVENT_TYPE, bounded),
        )
        rows = cursor.fetchall() or []
        for row in rows:
            message_id = _row_value(row, "id", 0, None)
            company_id = _company_id(_row_value(row, "company_id", 1, None))
            chat_id = _chat_id(_row_value(row, "chat_id", 2, ""))
            title = str(_row_value(row, "title", 3, "") or "")
            body = str(_row_value(row, "body", 4, "") or "")
            text = "\n\n".join(part for part in (title, body) if part).strip() or "Новая заявка"
            if dry_run:
                outcome["planned"].append({
                    "id": message_id,
                    "provider": "telegram",
                    "eventType": EVENT_TYPE,
                    "companyId": company_id,
                    "target": {"chatId": chat_id},
                })
                continue
            if not company_id or not chat_id:
                outcome["failed"].append({"id": message_id, "error": "telegram_target_missing"})
                continue
            try:
                provider_message_id = send_message(chat_id, text)
                cursor.execute(
                    """
                    UPDATE messenger_outbox
                       SET status='sent',
                           provider_message_id=%s,
                           sent_at=NOW(),
                           last_error='',
                           next_attempt_at=NULL,
                           updated_at=NOW()
                     WHERE id=%s
                       AND company_id=%s
                       AND provider='telegram'
                       AND event_type=%s
                    """,
                    (str(provider_message_id or "")[:255], message_id, company_id, EVENT_TYPE),
                )
                outcome["sent"].append({"id": message_id, "provider": "telegram", "companyId": company_id})
            except Exception as exc:
                error = "telegram_bot_token_missing" if str(exc) == "telegram_bot_token_missing" else "telegram_delivery_failed"
                if error == "telegram_bot_token_missing":
                    cursor.execute(
                        """
                        UPDATE messenger_outbox
                           SET last_error='telegram_bot_token_missing',
                               next_attempt_at=NOW() + INTERVAL '5 minutes',
                               updated_at=NOW()
                         WHERE id=%s
                           AND company_id=%s
                           AND provider='telegram'
                           AND event_type=%s
                           AND status='queued'
                        """,
                        (message_id, company_id, EVENT_TYPE),
                    )
                else:
                    cursor.execute(
                        """
                        UPDATE messenger_outbox
                           SET attempts=COALESCE(attempts,0)+1,
                               status=CASE
                                   WHEN COALESCE(attempts,0)+1 >= %s THEN 'failed'
                                   ELSE 'queued'
                               END,
                               last_error='telegram_delivery_failed',
                               failed_at=CASE
                                   WHEN COALESCE(attempts,0)+1 >= %s THEN NOW()
                                   ELSE failed_at
                               END,
                               next_attempt_at=NOW() + INTERVAL '5 minutes',
                               updated_at=NOW()
                         WHERE id=%s
                           AND company_id=%s
                           AND provider='telegram'
                           AND event_type=%s
                        """,
                        (MAX_ATTEMPTS, MAX_ATTEMPTS, message_id, company_id, EVENT_TYPE),
                    )
                outcome["failed"].append({"id": message_id, "error": error})
        cursor.execute(f"RELEASE SAVEPOINT {DISPATCH_SAVEPOINT}")
    except Exception:
        LOGGER.warning("crm_lead_telegram_dispatch_failed")
        try:
            cursor.execute(f"ROLLBACK TO SAVEPOINT {DISPATCH_SAVEPOINT}")
        except Exception:
            LOGGER.warning("crm_lead_telegram_dispatch_savepoint_failed")
    return outcome
