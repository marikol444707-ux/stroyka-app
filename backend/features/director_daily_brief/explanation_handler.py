"""Fail-closed optional handler for one exact daily-brief explanation."""

from collections.abc import Mapping

from psycopg2.extras import RealDictCursor

try:
    from backend.db import get_db
except ModuleNotFoundError:
    from db import get_db

from .explanation_model import generate_daily_brief_explanation
from .query_service import public_director_daily_brief


JOB_TYPE = "director.daily_brief.explanation"


class DirectorDailyBriefExplanationHandlerError(ValueError):
    pass


def _positive_int(value, field):
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise DirectorDailyBriefExplanationHandlerError(f"{field} must be a positive integer")
    return value


def read_daily_brief_explanation_source(
    company_id,
    source_job_id,
    *,
    connection_factory=get_db,
):
    company_id = _positive_int(company_id, "company_id")
    source_job_id = _positive_int(source_job_id, "source_job_id")
    connection = connection_factory()
    try:
        connection.set_session(readonly=True, autocommit=False)
        with connection.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """SELECT id,result_json
                     FROM agent_jobs
                    WHERE id=%s AND company_id=%s AND project_id IS NULL
                      AND job_type='director.daily_brief'
                      AND status='succeeded' AND completed_at IS NOT NULL
                      AND result_json IS NOT NULL
                    LIMIT 1""",
                (source_job_id, company_id),
            )
            row = cur.fetchone()
        connection.rollback()
    except BaseException:
        connection.rollback()
        raise
    finally:
        connection.close()
    if not row:
        raise DirectorDailyBriefExplanationHandlerError("daily brief source was not found")
    return {
        "sourceJobId": _positive_int(row.get("id"), "source_job_id"),
        "brief": public_director_daily_brief(row.get("result_json")),
    }


def _generate_with_config(*, brief, source_job_id):
    try:
        from backend.config import YANDEX_API_KEY, YANDEX_FOLDER_ID
    except ModuleNotFoundError:
        from config import YANDEX_API_KEY, YANDEX_FOLDER_ID

    return generate_daily_brief_explanation(
        brief=brief,
        source_job_id=source_job_id,
        api_key=YANDEX_API_KEY,
        folder_id=YANDEX_FOLDER_ID,
    )


def build_daily_brief_explanation_handler(
    *,
    read_source=read_daily_brief_explanation_source,
    generate_explanation=_generate_with_config,
):
    if not callable(read_source) or not callable(generate_explanation):
        raise DirectorDailyBriefExplanationHandlerError("handler dependencies must be callable")

    def handle(context):
        if context.job_type != JOB_TYPE:
            raise DirectorDailyBriefExplanationHandlerError("handler received the wrong job type")
        if context.project_id is not None:
            raise DirectorDailyBriefExplanationHandlerError("explanation must use company scope")
        if set(context.payload) != {"sourceJobId"}:
            raise DirectorDailyBriefExplanationHandlerError("explanation payload is invalid")
        source_job_id = _positive_int(context.payload["sourceJobId"], "source_job_id")
        source = read_source(context.owner_company_id, source_job_id)
        if (
            not isinstance(source, Mapping)
            or set(source) != {"sourceJobId", "brief"}
            or source.get("sourceJobId") != source_job_id
        ):
            raise DirectorDailyBriefExplanationHandlerError("daily brief source identity drifted")
        brief = public_director_daily_brief(source.get("brief"))
        return generate_explanation(brief=brief, source_job_id=source_job_id)

    return handle


# Deliberately not registered in the default worker registry until A4.3b rollout.
handle_daily_brief_explanation = build_daily_brief_explanation_handler()
