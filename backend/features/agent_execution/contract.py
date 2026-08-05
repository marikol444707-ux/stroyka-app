import json
import re
from dataclasses import dataclass
from datetime import date
from types import MappingProxyType

from backend.features.agent_jobs.service import (
    AgentJobValidationError,
    serialize_safe_json_object,
)
from backend.features.director_agent.policy import DIRECTOR_AGENT_READ_TOOLS
from backend.features.director_agent.result_policy import (
    DirectorAgentResultPolicyError,
    sanitize_director_agent_tool_result,
)


class AgentExecutionContractError(ValueError):
    pass


@dataclass(frozen=True)
class AgentExecutionContract:
    job_type: str
    version: int
    allowed_tools: tuple
    allowed_model_fields: tuple
    required_model_fields: tuple
    read_only: bool
    database_access: str
    timeout_seconds: int
    max_model_calls: int
    max_tool_calls: int
    max_input_bytes: int
    max_output_tokens: int
    cost_currency: str
    max_cost_minor_units: int


@dataclass(frozen=True)
class PreparedAgentExecution:
    contract: AgentExecutionContract
    owner_company_id: int
    requested_tools: tuple
    model_payload_json: str


_DAILY_BRIEF_CONTRACT = AgentExecutionContract(
    job_type="director.daily_brief",
    version=1,
    allowed_tools=DIRECTOR_AGENT_READ_TOOLS,
    allowed_model_fields=("briefDate", "companyName", "sections", "facts"),
    required_model_fields=("briefDate", "facts"),
    read_only=True,
    database_access="none",
    timeout_seconds=45,
    max_model_calls=2,
    max_tool_calls=7,
    max_input_bytes=32 * 1024,
    max_output_tokens=1600,
    cost_currency="RUB",
    max_cost_minor_units=500,
)

AGENT_EXECUTION_CONTRACTS = MappingProxyType({
    _DAILY_BRIEF_CONTRACT.job_type: _DAILY_BRIEF_CONTRACT,
})

_FORBIDDEN_MODEL_CONTEXT_KEYS = {
    "companyid",
    "companyids",
    "connection",
    "credentials",
    "cursor",
    "databaserows",
    "rawdatabaserows",
    "rawrows",
    "sql",
    "tenantid",
    "tenantids",
}
_SENSITIVE_MODEL_VALUE_RE = re.compile(
    r"(?:\bBearer\s+\S+|-----BEGIN [A-Z ]*PRIVATE KEY-----|\bsk[-_][A-Za-z0-9_-]{8,}\b)",
    re.IGNORECASE,
)


def get_execution_contract(job_type):
    normalized = str(job_type or "").strip()
    contract = AGENT_EXECUTION_CONTRACTS.get(normalized)
    if contract is None:
        raise AgentExecutionContractError("job type has no execution contract")
    return contract


def _owner_company_id(value):
    if type(value) is not int or value <= 0:
        raise AgentExecutionContractError("owner_company_id must be one positive company id")
    return value


def _contains_forbidden_model_context(value):
    if isinstance(value, dict):
        for key, nested in value.items():
            normalized_key = re.sub(r"[^a-z0-9]", "", str(key).lower())
            if normalized_key in _FORBIDDEN_MODEL_CONTEXT_KEYS:
                return True
            if normalized_key.startswith("raw") and normalized_key.endswith("rows"):
                return True
            if _contains_forbidden_model_context(nested):
                return True
    elif isinstance(value, (list, tuple)):
        return any(_contains_forbidden_model_context(item) for item in value)
    elif isinstance(value, str):
        return bool(_SENSITIVE_MODEL_VALUE_RE.search(value))
    return False


def _requested_tools(contract, values):
    if values is None or isinstance(values, str) or not isinstance(values, (list, tuple)):
        raise AgentExecutionContractError("requested_tools must be an explicit list")
    normalized = []
    for value in values:
        tool = str(value or "").strip()
        if tool not in contract.allowed_tools:
            raise AgentExecutionContractError("requested tool is not allowed")
        if tool not in normalized:
            normalized.append(tool)
    if len(normalized) > contract.max_tool_calls:
        raise AgentExecutionContractError("requested tools exceed the contract limit")
    return tuple(normalized)


def _model_payload_json(contract, value):
    if not isinstance(value, dict):
        raise AgentExecutionContractError("model_payload must be an object")
    unknown_fields = set(value).difference(contract.allowed_model_fields)
    if unknown_fields:
        raise AgentExecutionContractError("model_payload contains fields outside the contract")
    missing_fields = set(contract.required_model_fields).difference(value)
    if missing_fields:
        raise AgentExecutionContractError("model_payload is missing required fields")
    brief_date = value.get("briefDate")
    if not isinstance(brief_date, str):
        raise AgentExecutionContractError("briefDate must be an ISO date")
    try:
        if date.fromisoformat(brief_date).isoformat() != brief_date:
            raise ValueError
    except ValueError as exc:
        raise AgentExecutionContractError("briefDate must be an ISO date") from exc
    company_name = value.get("companyName")
    if company_name is not None and (
        not isinstance(company_name, str) or not company_name.strip() or len(company_name) > 200
    ):
        raise AgentExecutionContractError("companyName must be a non-empty string up to 200 characters")
    sections = value.get("sections", [])
    if not isinstance(sections, list) or any(section not in contract.allowed_tools for section in sections):
        raise AgentExecutionContractError("sections must contain only allowed tool names")
    if len(set(sections)) != len(sections):
        raise AgentExecutionContractError("sections must not contain duplicates")
    facts = value.get("facts")
    if not isinstance(facts, dict):
        raise AgentExecutionContractError("facts must be an object")
    try:
        sanitized_facts = {
            tool_name: sanitize_director_agent_tool_result(tool_name, result)
            for tool_name, result in facts.items()
        }
    except DirectorAgentResultPolicyError as exc:
        raise AgentExecutionContractError(str(exc)) from exc
    value = dict(value)
    value["facts"] = sanitized_facts
    if _contains_forbidden_model_context(value):
        raise AgentExecutionContractError("model_payload contains forbidden database or secret context")
    try:
        serialized = serialize_safe_json_object(value, field="model_payload")
    except AgentJobValidationError as exc:
        raise AgentExecutionContractError(str(exc)) from exc
    canonical = json.dumps(
        json.loads(serialized),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
        allow_nan=False,
    )
    if len(canonical.encode("utf-8")) > contract.max_input_bytes:
        raise AgentExecutionContractError("model_payload exceeds the contract limit")
    return canonical


def prepare_agent_execution(*, job_type, owner_company_id, requested_tools, model_payload):
    contract = get_execution_contract(job_type)
    owner_company_id = _owner_company_id(owner_company_id)
    normalized_tools = _requested_tools(contract, requested_tools)
    model_payload_json = _model_payload_json(contract, model_payload)
    normalized_payload = json.loads(model_payload_json)
    payload_tools = set(normalized_payload.get("sections", [])) | set(normalized_payload["facts"])
    if not payload_tools.issubset(normalized_tools):
        raise AgentExecutionContractError("model_payload contains tools that were not requested")
    return PreparedAgentExecution(
        contract=contract,
        owner_company_id=owner_company_id,
        requested_tools=normalized_tools,
        model_payload_json=model_payload_json,
    )
