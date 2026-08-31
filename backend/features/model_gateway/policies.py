"""Closed logical capability policies for the provider-neutral gateway."""

from dataclasses import dataclass
from types import MappingProxyType


@dataclass(frozen=True)
class ModelCapabilityPolicy:
    capability: str
    model_policy: str
    allowed_input_kinds: tuple
    max_input_bytes: int
    max_output_tokens: int
    max_parts: int


def _policy(
    capability,
    *,
    model_policy="balanced_text",
    multipart=False,
    file_data_url=False,
    max_input_bytes=256 * 1024,
    max_output_tokens=8_000,
):
    allowed_input_kinds = ("text", "image_data_url", "file_id")
    if file_data_url:
        allowed_input_kinds += ("file_data_url",)
    return ModelCapabilityPolicy(
        capability=capability,
        model_policy=model_policy,
        allowed_input_kinds=allowed_input_kinds if multipart else ("text",),
        max_input_bytes=max_input_bytes,
        max_output_tokens=max_output_tokens,
        max_parts=16 if multipart else 1,
    )


_CAPABILITIES = (
    _policy("ai_chat"),
    _policy("cable_journal_suggestion", model_policy="strict_json"),
    _policy("director_agent", model_policy="low_cost_text"),
    _policy(
        "document_recognition",
        model_policy="strict_json",
        max_input_bytes=512 * 1024,
    ),
    _policy("estimate_change_price", model_policy="strict_json"),
    _policy("estimate_chat"),
    _policy("estimate_distribution", model_policy="strict_json"),
    _policy("estimate_generation", model_policy="strict_json"),
    _policy("hidden_works_act_prefill", model_policy="strict_json"),
    _policy("hidden_works_detection", model_policy="strict_json"),
    _policy(
        "invoice_scan",
        model_policy="vision_json",
        multipart=True,
        max_input_bytes=4 * 1024 * 1024,
        max_output_tokens=12_000,
    ),
    _policy("material_inspection_suggestion", model_policy="strict_json"),
    _policy("material_norm_suggestion", model_policy="strict_json"),
    _policy(
        "platform_client_card",
        model_policy="vision_json",
        multipart=True,
        file_data_url=True,
        max_input_bytes=17 * 1024 * 1024,
    ),
    _policy("pricelist_generation", model_policy="strict_json"),
    _policy(
        "project_room_draft",
        model_policy="vision_json",
        multipart=True,
        max_input_bytes=4 * 1024 * 1024,
    ),
    _policy("supply_delivery_check", model_policy="strict_json"),
    _policy("supply_kp_comparison", model_policy="strict_json"),
    _policy("tb_instruction"),
    _policy("work_journal_prefill", model_policy="strict_json"),
)

MODEL_CAPABILITIES = MappingProxyType({
    policy.capability: policy
    for policy in _CAPABILITIES
})

if len(MODEL_CAPABILITIES) != len(_CAPABILITIES):
    raise RuntimeError("model gateway capabilities must be unique")
