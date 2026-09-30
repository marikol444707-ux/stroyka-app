"""Pure, fail-closed contract for optional daily-brief model explanations."""

import json
import re
from collections.abc import Mapping

from .query_service import DirectorDailyBriefQueryError, public_director_daily_brief


class DirectorDailyBriefExplanationError(ValueError):
    pass


_MAX_INPUT_BYTES = 32 * 1024
_TEXT_LIMITS = {"headline": 160, "overview": 600, "point": 240}
_UNSAFE_TEXT = re.compile(r"[<>\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_DIGIT = re.compile(r"\d")


def _public_brief(value):
    try:
        return public_director_daily_brief(value)
    except DirectorDailyBriefQueryError as exc:
        raise DirectorDailyBriefExplanationError("daily brief is invalid") from exc


def _positive_int(value, field):
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise DirectorDailyBriefExplanationError(f"{field} must be a positive integer")
    return value


def _model_text(value, field, limit):
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise DirectorDailyBriefExplanationError(f"{field} must be bounded text")
    if len(value) > limit or _UNSAFE_TEXT.search(value) or _DIGIT.search(value):
        raise DirectorDailyBriefExplanationError(f"{field} contains unsafe text")
    return value


def build_explanation_model_input(brief):
    """Return canonical JSON containing only the public deterministic facts."""
    public = _public_brief(brief)
    payload = {
        "schemaVersion": public["schemaVersion"],
        "briefDate": public["briefDate"],
        "summary": public["summary"],
        "sections": public["sections"],
    }
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    if len(encoded.encode("utf-8")) > _MAX_INPUT_BYTES:
        raise DirectorDailyBriefExplanationError("daily brief model input is too large")
    return encoded


def parse_explanation_model_output(output_text, *, source_job_id, brief):
    """Validate untrusted model JSON and bind it to one exact source job."""
    source_job_id = _positive_int(source_job_id, "source_job_id")
    public = _public_brief(brief)
    if not isinstance(output_text, str) or len(output_text.encode("utf-8")) > 4096:
        raise DirectorDailyBriefExplanationError("model output is invalid")
    try:
        value = json.loads(output_text)
    except (TypeError, ValueError) as exc:
        raise DirectorDailyBriefExplanationError("model output is not JSON") from exc
    if not isinstance(value, Mapping) or set(value) != {"headline", "overview", "points"}:
        raise DirectorDailyBriefExplanationError("model output fields are invalid")
    return _validated_explanation(value, source_job_id=source_job_id, public=public)


def _validated_explanation(value, *, source_job_id, public):
    points = value["points"]
    if not isinstance(points, list) or len(points) > 5:
        raise DirectorDailyBriefExplanationError("model output points are invalid")
    source_codes = {
        item["code"]
        for section in public["sections"]
        for item in section["items"]
    }
    seen = set()
    normalized_points = []
    for index, point in enumerate(points):
        if not isinstance(point, Mapping) or set(point) != {"sourceCode", "text"}:
            raise DirectorDailyBriefExplanationError("model output point fields are invalid")
        code = point["sourceCode"]
        if not isinstance(code, str) or code not in source_codes or code in seen:
            raise DirectorDailyBriefExplanationError("model output source code is invalid")
        seen.add(code)
        normalized_points.append({
            "sourceCode": code,
            "text": _model_text(point["text"], f"points[{index}].text", _TEXT_LIMITS["point"]),
        })
    return {
        "schemaVersion": 1,
        "sourceJobId": source_job_id,
        "headline": _model_text(value["headline"], "headline", _TEXT_LIMITS["headline"]),
        "overview": _model_text(value["overview"], "overview", _TEXT_LIMITS["overview"]),
        "points": normalized_points,
    }


def public_daily_brief_explanation(value, *, source_job_id, brief):
    """Validate one stored explanation against its exact public source brief."""
    source_job_id = _positive_int(source_job_id, "source_job_id")
    public = _public_brief(brief)
    if not isinstance(value, Mapping) or set(value) != {
        "schemaVersion", "sourceJobId", "headline", "overview", "points"
    }:
        raise DirectorDailyBriefExplanationError("stored explanation fields are invalid")
    if value.get("schemaVersion") != 1 or value.get("sourceJobId") != source_job_id:
        raise DirectorDailyBriefExplanationError("stored explanation source is invalid")
    generated = {
        "headline": value.get("headline"),
        "overview": value.get("overview"),
        "points": value.get("points"),
    }
    return _validated_explanation(generated, source_job_id=source_job_id, public=public)
