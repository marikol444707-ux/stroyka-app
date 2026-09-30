"""Explicit, idempotent MAX delivery for one validated brief explanation."""

import json
from collections.abc import Mapping

from .explanation_contract import public_daily_brief_explanation


class DirectorDailyBriefExplanationMaxDeliveryError(ValueError):
    pass


_EVENT_TYPE = "director_daily_brief_explanation_ready"
_ENTITY_TYPE = "director_daily_brief_explanation"
_LOCK_NAMESPACE = 4405


def _positive_int(value, field):
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise DirectorDailyBriefExplanationMaxDeliveryError(
            f"{field} must be a positive integer"
        )
    return value


def _message(explanation):
    lines = [explanation["headline"], "", explanation["overview"]]
    lines.extend(f"• {point['text']}" for point in explanation["points"])
    lines.extend(("", "Открыть сводку: https://stroyka26.pro/app"))
    body = "\n".join(lines)
    if len(body) > 3500:
        raise DirectorDailyBriefExplanationMaxDeliveryError("MAX message is too long")
    return body


def prepare_daily_brief_explanation_max_delivery(
    cur,
    *,
    company_id,
    explanation_job_id,
    recipient_user_id,
    enabled=False,
    apply=False,
):
    company_id = _positive_int(company_id, "company_id")
    explanation_job_id = _positive_int(explanation_job_id, "explanation_job_id")
    recipient_user_id = _positive_int(recipient_user_id, "recipient_user_id")
    if type(enabled) is not bool or type(apply) is not bool:
        raise DirectorDailyBriefExplanationMaxDeliveryError("delivery controls are invalid")
    report = {
        "ok": True,
        "dryRun": not apply,
        "writesAttempted": 0,
        "companyId": company_id,
        "explanationJobId": explanation_job_id,
        "recipientUserId": recipient_user_id,
    }
    if not enabled:
        report["state"] = "disabled"
        return report

    cur.execute(
        """SELECT explanation.id,explanation.payload_json,explanation.result_json
             FROM agent_jobs explanation
            WHERE explanation.id=%s AND explanation.company_id=%s
              AND explanation.project_id IS NULL
              AND explanation.job_type='director.daily_brief.explanation'
              AND explanation.status='succeeded'
            LIMIT 1""",
        (explanation_job_id, company_id),
    )
    explanation_row = cur.fetchone()
    if (
        not isinstance(explanation_row, Mapping)
        or explanation_row.get("id") != explanation_job_id
    ):
        raise DirectorDailyBriefExplanationMaxDeliveryError("explanation was not found")
    payload = explanation_row.get("payload_json")
    if not isinstance(payload, Mapping) or set(payload) != {"sourceJobId"}:
        raise DirectorDailyBriefExplanationMaxDeliveryError("explanation payload is invalid")
    source_job_id = _positive_int(payload.get("sourceJobId"), "source_job_id")
    cur.execute(
        """SELECT id,result_json
             FROM agent_jobs
            WHERE id=%s AND company_id=%s AND project_id IS NULL
              AND job_type='director.daily_brief' AND status='succeeded'
              AND completed_at IS NOT NULL AND result_json IS NOT NULL
            LIMIT 1""",
        (source_job_id, company_id),
    )
    source_row = cur.fetchone()
    if not isinstance(source_row, Mapping) or source_row.get("id") != source_job_id:
        raise DirectorDailyBriefExplanationMaxDeliveryError("daily brief source was not found")
    explanation = public_daily_brief_explanation(
        explanation_row.get("result_json"),
        source_job_id=source_job_id,
        brief=source_row.get("result_json"),
    )

    cur.execute(
        """SELECT account.id,account.user_id,account.external_user_id,account.chat_id
             FROM messenger_accounts account
            WHERE account.user_id=%s AND account.provider='max'
              AND COALESCE(account.enabled,TRUE)=TRUE
              AND account.verified_at IS NOT NULL
              AND (COALESCE(account.chat_id,'')<>''
                   OR COALESCE(account.external_user_id,'')<>'')
              AND EXISTS (
                    SELECT 1 FROM user_company_roles membership
                     WHERE membership.company_id=%s
                       AND membership.user_id=account.user_id
                       AND membership.active IS TRUE
                       AND membership.role IN ('директор','зам_директора')
              )
            ORDER BY account.id LIMIT 2""",
        (recipient_user_id, company_id),
    )
    accounts = cur.fetchall()
    if len(accounts) != 1:
        raise DirectorDailyBriefExplanationMaxDeliveryError(
            "recipient must have exactly one active verified MAX account"
        )
    account = accounts[0]

    if apply:
        cur.execute(
            "SELECT pg_advisory_xact_lock(%s,%s)",
            (_LOCK_NAMESPACE, explanation_job_id),
        )
        cur.fetchone()
    cur.execute(
        """SELECT id,status FROM messenger_outbox
            WHERE owner_scope='company' AND company_id=%s AND provider='max'
              AND user_id=%s AND event_type=%s
              AND entity_type=%s AND entity_id=%s
            ORDER BY id DESC LIMIT 1""",
        (company_id, recipient_user_id, _EVENT_TYPE, _ENTITY_TYPE, explanation_job_id),
    )
    existing = cur.fetchone()
    if existing:
        report.update({"state": "existing", "outboxId": _positive_int(existing.get("id"), "outbox_id")})
        return report
    if not apply:
        report["state"] = "would_enqueue"
        return report

    body = _message(explanation)
    payload = json.dumps(
        {"sourceJobId": source_job_id, "explanationJobId": explanation_job_id},
        ensure_ascii=False,
        separators=(",", ":"),
    )
    cur.execute(
        """INSERT INTO messenger_outbox
              (owner_scope,company_id,project_id,provider,messenger_account_id,
               user_id,external_user_id,chat_id,event_type,entity_type,entity_id,
               title,body,payload_json,actions_json,status,priority)
            VALUES ('company',%s,NULL,'max',%s,%s,%s,%s,%s,%s,%s,%s,%s,
                    %s::jsonb,%s::jsonb,'queued',%s)
            RETURNING id""",
        (
            company_id,
            account.get("id"),
            recipient_user_id,
            account.get("external_user_id") or "",
            account.get("chat_id") or account.get("external_user_id") or "",
            _EVENT_TYPE,
            _ENTITY_TYPE,
            explanation_job_id,
            "Директорская сводка готова",
            body,
            payload,
            "[]",
            5,
        ),
    )
    inserted = cur.fetchone()
    report.update({
        "state": "enqueued",
        "writesAttempted": 1,
        "outboxId": _positive_int(inserted.get("id"), "outbox_id"),
    })
    return report
