"""Fail-closed queue handler for the deterministic director daily brief."""

from collections.abc import Mapping

try:
    from backend.features.director_daily_brief.service import build_director_daily_brief
except ModuleNotFoundError:
    from features.director_daily_brief.service import build_director_daily_brief


class DirectorDailyBriefHandlerError(ValueError):
    pass


def _default_read_results(company_id):
    try:
        from backend.features.director_agent.read_tools import (
            read_director_agent_tool_results,
        )
    except ModuleNotFoundError:
        from features.director_agent.read_tools import read_director_agent_tool_results

    return read_director_agent_tool_results(company_id=company_id)


def build_director_daily_brief_handler(*, read_results=_default_read_results):
    if not callable(read_results):
        raise DirectorDailyBriefHandlerError("read_results must be callable")
    read_results_dependency = read_results

    def handle(context):
        if context.job_type != "director.daily_brief":
            raise DirectorDailyBriefHandlerError("handler received the wrong job type")
        if context.project_id is not None:
            raise DirectorDailyBriefHandlerError("daily brief must use company scope")
        if set(context.payload) != {"briefDate"}:
            raise DirectorDailyBriefHandlerError("daily brief payload must contain only briefDate")
        tool_results = read_results_dependency(context.owner_company_id)
        if not isinstance(tool_results, Mapping):
            raise DirectorDailyBriefHandlerError("read results must be an object")
        return build_director_daily_brief(
            brief_date=context.payload["briefDate"],
            tool_results=tool_results,
        )

    return handle


handle_director_daily_brief = build_director_daily_brief_handler()
