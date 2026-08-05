import math
from types import MappingProxyType

try:
    from backend.features.director_agent.policy import DIRECTOR_AGENT_READ_TOOLS
except ModuleNotFoundError:
    from features.director_agent.policy import DIRECTOR_AGENT_READ_TOOLS


class DirectorAgentResultPolicyError(ValueError):
    pass


def _field(name, kind, limit=0):
    return (name, kind, limit)


_LIST_RESULT_SCHEMAS = MappingProxyType({
    "projects": (
        (_field("name", "text", 300), _field("status", "text", 100),
         _field("budget", "float"), _field("progress", "int"),
         _field("deadline", "text", 40)),
        40,
    ),
    "estimates": (
        (_field("name", "text", 300), _field("project", "text", 300),
         _field("version", "text", 80), _field("status", "text", 100),
         _field("type", "text", 100), _field("package", "text", 200),
         _field("items", "int"), _field("workItems", "int"),
         _field("materialItems", "int"), _field("total", "float")),
        30,
    ),
    "finances": (
        (_field("project", "text", 300), _field("status", "text", 100),
         _field("budget", "float"), _field("paymentsNet", "float"),
         _field("manualExpenses", "nullable_float"),
         _field("manualExpensesScoped", "bool")),
        40,
    ),
})

_OBJECT_RESULT_SCHEMAS = MappingProxyType({
    "warehouse": (
        ("mainWarehouse",
         (_field("name", "text", 300), _field("qty", "float"),
          _field("unit", "text", 40), _field("minQty", "float"),
          _field("category", "text", 120)), 40),
        ("objectMaterials",
         (_field("project", "text", 300), _field("name", "text", 300),
          _field("qty", "float"), _field("unit", "text", 40),
          _field("category", "text", 120)), 60),
    ),
    "supply": (
        ("requestStatusCounts", "count_map", 40),
        ("recentRequests",
         (_field("project", "text", 300), _field("material", "text", 300),
          _field("qty", "float"), _field("unit", "text", 40),
          _field("status", "text", 100), _field("urgency", "text", 100)), 25),
        ("recentDeliveries",
         (_field("project", "text", 300), _field("material", "text", 300),
          _field("planned", "float"), _field("shipped", "float"),
          _field("received", "float"), _field("unit", "text", 40),
          _field("supplier", "text", 300), _field("status", "text", 100),
          _field("quality", "text", 100)), 25),
        ("openClaims",
         (_field("project", "text", 300), _field("material", "text", 300),
          _field("type", "text", 100), _field("status", "text", 100),
          _field("shortage", "float")), 20),
    ),
    "staff": (
        ("roleCounts", (_field("role", "text", 100), _field("count", "int")), 50),
        ("staff",
         (_field("name", "text", 200), _field("role", "text", 100),
          _field("project", "text", 300), _field("specialization", "text", 200)), 80),
    ),
    "ai_tasks": (
        ("openStatusCounts", "count_map", 40),
        ("tasks",
         (_field("project", "text", 300), _field("title", "text", 500),
          _field("assignedRole", "text", 100), _field("assignedTo", "text", 200),
          _field("status", "text", 100), _field("dueDate", "text", 40)), 30),
    ),
})


def _scalar(value, kind, limit):
    if kind == "text":
        if value is None:
            return ""
        if not isinstance(value, str):
            raise DirectorAgentResultPolicyError("tool result text field has an invalid type")
        if len(value) > limit:
            raise DirectorAgentResultPolicyError("tool result text field is too long")
        return value
    if kind == "bool":
        if type(value) is not bool:
            raise DirectorAgentResultPolicyError("tool result boolean field has an invalid type")
        return value
    if kind == "nullable_float" and value is None:
        return None
    if kind in ("float", "nullable_float"):
        if isinstance(value, bool):
            raise DirectorAgentResultPolicyError("tool result number field has an invalid type")
        try:
            normalized = float(value or 0)
        except (TypeError, ValueError) as exc:
            raise DirectorAgentResultPolicyError("tool result number field has an invalid type") from exc
        if not math.isfinite(normalized):
            raise DirectorAgentResultPolicyError("tool result number field is not finite")
        return normalized
    if kind == "int":
        if isinstance(value, bool):
            raise DirectorAgentResultPolicyError("tool result integer field has an invalid type")
        try:
            normalized = int(value or 0)
        except (TypeError, ValueError) as exc:
            raise DirectorAgentResultPolicyError("tool result integer field has an invalid type") from exc
        if normalized < 0:
            raise DirectorAgentResultPolicyError("tool result integer field must not be negative")
        return normalized
    raise DirectorAgentResultPolicyError("unknown tool result field type")


def _record(value, fields):
    if not isinstance(value, dict):
        raise DirectorAgentResultPolicyError("tool result record must be an object")
    missing = [name for name, _kind, _limit in fields if name not in value]
    if missing:
        raise DirectorAgentResultPolicyError("tool result record is missing required fields")
    return {
        name: _scalar(value.get(name), kind, limit)
        for name, kind, limit in fields
    }


def _records(value, fields, limit):
    if not isinstance(value, list):
        raise DirectorAgentResultPolicyError("tool result must be a list")
    if len(value) > limit:
        raise DirectorAgentResultPolicyError("tool result contains too many records")
    return [_record(item, fields) for item in value]


def _count_map(value, limit):
    if not isinstance(value, dict) or len(value) > limit:
        raise DirectorAgentResultPolicyError("tool result count map is invalid")
    result = {}
    for key, count in value.items():
        normalized_key = _scalar(key, "text", 100)
        result[normalized_key] = _scalar(count, "int", 0)
    return result


def sanitize_director_agent_tool_result(tool_name, value):
    if tool_name not in DIRECTOR_AGENT_READ_TOOLS:
        raise DirectorAgentResultPolicyError("tool has no result policy")
    list_schema = _LIST_RESULT_SCHEMAS.get(tool_name)
    if list_schema is not None:
        return _records(value, *list_schema)
    if not isinstance(value, dict):
        raise DirectorAgentResultPolicyError("tool result must be an object")
    result = {}
    for key, fields, limit in _OBJECT_RESULT_SCHEMAS[tool_name]:
        if key not in value:
            raise DirectorAgentResultPolicyError("tool result is missing a required section")
        nested = value[key]
        result[key] = _count_map(nested, limit) if fields == "count_map" else _records(nested, fields, limit)
    return result
