"""Pure preparation, validation and finalization for one A9.2 preview."""

import hashlib
import json
import math
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

from backend.features.estimate_revision_impact.combined_contract import (
    build_combined_report,
    calculate_evidence_sha256,
)
from backend.features.estimate_revision_impact.contract import (
    EVENT_TYPE,
    REPORT_VERSION,
    EstimateRevisionImpactContractError,
    EstimateRevisionSource,
    validate_estimate_revision_source,
)
from backend.features.warehouse_recommendation_preview.readiness import (
    WAREHOUSE_ANOMALY_READINESS_VERSION,
    build_warehouse_anomaly_readiness,
)


_MAX_STORED_REPORT_CANONICAL_BYTES = 4 * 1024 * 1024
_RELEVANT_EVIDENCE_VERSION = 1
WAREHOUSE_ANOMALY_CONTENT_VERSION = 1
_SELECTION_FIELDS = frozenset({
    "subjectKind",
    "subjectId",
    "anomalyCode",
})
_SELECTION_RULES = MappingProxyType({
    "warehouse_invoice_request_mismatch": "warehouseInvoice",
    "warehouse_invoice_project_mismatch": "warehouseInvoice",
    "warehouse_invoice_delivery_mismatch": "warehouseInvoice",
    "warehouse_invoice_supplier_invoice_mismatch": "warehouseInvoice",
    "warehouse_invoice_items_invalid": "warehouseInvoice",
    "warehouse_receipt_invoice_mismatch": "warehouseHistory",
    "warehouse_receipt_line_invalid": "warehouseHistory",
    "warehouse_receipt_package_mismatch": "warehouseHistory",
    "warehouse_receipt_lot_invoice_mismatch": "receiptLot",
    "warehouse_receipt_lot_line_invalid": "receiptLot",
    "warehouse_receipt_lot_project_mismatch": "receiptLot",
    "warehouse_movement_invoice_mismatch": "warehouseMovement",
    "warehouse_movement_line_invalid": "warehouseMovement",
    "warehouse_movement_package_mismatch": "warehouseMovement",
    "warehouse_movement_lot_missing": "warehouseMovement",
    "warehouse_lot_movement_missing": "warehouseMovement",
    "warehouse_lot_movement_parent_mismatch": "lotMovement",
    "warehouse_lot_movement_source_mismatch": "lotMovement",
})
_ANOMALY_RECOMMENDATION_RULES = MappingProxyType({
    "warehouse_invoice_request_mismatch": (
        "review_warehouse_invoice_lineage"
    ),
    "warehouse_invoice_project_mismatch": (
        "review_warehouse_invoice_lineage"
    ),
    "warehouse_invoice_delivery_mismatch": (
        "review_warehouse_invoice_lineage"
    ),
    "warehouse_invoice_supplier_invoice_mismatch": (
        "review_warehouse_invoice_lineage"
    ),
    "warehouse_invoice_items_invalid": "review_warehouse_invoice_items",
    "warehouse_receipt_invoice_mismatch": (
        "review_warehouse_receipt_lineage"
    ),
    "warehouse_receipt_line_invalid": "review_warehouse_receipt_lineage",
    "warehouse_receipt_package_mismatch": (
        "review_warehouse_receipt_lineage"
    ),
    "warehouse_receipt_lot_invoice_mismatch": (
        "review_receipt_lot_lineage"
    ),
    "warehouse_receipt_lot_line_invalid": "review_receipt_lot_lineage",
    "warehouse_receipt_lot_project_mismatch": (
        "review_receipt_lot_lineage"
    ),
    "warehouse_movement_invoice_mismatch": (
        "review_warehouse_movement_lineage"
    ),
    "warehouse_movement_line_invalid": (
        "review_warehouse_movement_lineage"
    ),
    "warehouse_movement_package_mismatch": (
        "review_warehouse_movement_lineage"
    ),
    "warehouse_movement_lot_missing": (
        "review_warehouse_movement_traceability"
    ),
    "warehouse_lot_movement_missing": (
        "review_warehouse_movement_traceability"
    ),
    "warehouse_lot_movement_parent_mismatch": (
        "review_lot_movement_lineage"
    ),
    "warehouse_lot_movement_source_mismatch": (
        "review_lot_movement_lineage"
    ),
})
_FIXED_FINDINGS = MappingProxyType({
    "warehouse_invoice_request_mismatch": (
        "Связь складской накладной с заявкой не совпадает с текущей "
        "точной цепочкой источника."
    ),
    "warehouse_invoice_project_mismatch": (
        "Проект складской накладной не совпадает с текущей точной "
        "цепочкой источника."
    ),
    "warehouse_invoice_delivery_mismatch": (
        "Связь складской накладной с поставкой не совпадает с текущей "
        "точной цепочкой источника."
    ),
    "warehouse_invoice_supplier_invoice_mismatch": (
        "Связь складской накладной с документом поставщика не совпадает "
        "с текущей точной цепочкой источника."
    ),
    "warehouse_invoice_items_invalid": (
        "Состав строк складской накладной не подтверждён текущим точным "
        "snapshot."
    ),
    "warehouse_receipt_invoice_mismatch": (
        "Приход склада не связан с ожидаемой накладной в текущем точном "
        "snapshot."
    ),
    "warehouse_receipt_line_invalid": (
        "Строка-источник складского прихода отсутствует или невалидна "
        "в текущем точном snapshot."
    ),
    "warehouse_receipt_package_mismatch": (
        "Пакет работ складского прихода не совпадает с текущей точной "
        "цепочкой источника."
    ),
    "warehouse_receipt_lot_invoice_mismatch": (
        "Партия прихода не связана с ожидаемой накладной в текущем "
        "точном snapshot."
    ),
    "warehouse_receipt_lot_line_invalid": (
        "Строка-источник партии прихода отсутствует или невалидна в "
        "текущем точном snapshot."
    ),
    "warehouse_receipt_lot_project_mismatch": (
        "Проект партии прихода не совпадает с текущей точной цепочкой "
        "источника."
    ),
    "warehouse_movement_invoice_mismatch": (
        "Движение склада не связано с ожидаемой накладной в текущем "
        "точном snapshot."
    ),
    "warehouse_movement_line_invalid": (
        "Строка-источник движения склада отсутствует или невалидна в "
        "текущем точном snapshot."
    ),
    "warehouse_movement_package_mismatch": (
        "Пакет работ движения склада не совпадает с текущей точной "
        "цепочкой источника."
    ),
    "warehouse_movement_lot_missing": (
        "Для движения склада не найдена ожидаемая связь с партией "
        "прихода."
    ),
    "warehouse_lot_movement_missing": (
        "Для связи партии не найдено ожидаемое складское движение."
    ),
    "warehouse_lot_movement_parent_mismatch": (
        "Родительская связь события партии не совпадает с текущим "
        "точным snapshot."
    ),
    "warehouse_lot_movement_source_mismatch": (
        "Источник события партии не совпадает с текущим точным snapshot."
    ),
})
_FIXED_RECOMMENDATION_CONTENT = MappingProxyType({
    "review_warehouse_invoice_lineage": (
        "Проверить связь складской накладной",
        "Сверьте первичный документ и его точные связи. Не меняйте "
        "остаток автоматически.",
    ),
    "review_warehouse_invoice_items": (
        "Проверить состав складской накладной",
        "Сверьте строки первичного документа с источником. Не исправляйте "
        "количество автоматически.",
    ),
    "review_warehouse_receipt_lineage": (
        "Проверить связь складского прихода",
        "Сверьте приход с накладной, строкой и пакетом работ. Не создавайте "
        "корректирующее движение автоматически.",
    ),
    "review_receipt_lot_lineage": (
        "Проверить связь партии прихода",
        "Сверьте партию с накладной, строкой и проектом. Не меняйте "
        "доступное количество автоматически.",
    ),
    "review_warehouse_movement_lineage": (
        "Проверить источник движения склада",
        "Сверьте движение с накладной, строкой и пакетом работ. Не "
        "отменяйте и не повторяйте движение автоматически.",
    ),
    "review_warehouse_movement_traceability": (
        "Проверить трассируемость движения склада",
        "Сверьте движение и событие партии по первичным ID. Не "
        "восстанавливайте связь автоматически.",
    ),
    "review_lot_movement_lineage": (
        "Проверить событие партии",
        "Сверьте родительское движение и источник события партии. Не "
        "перепривязывайте событие автоматически.",
    ),
})
_STORED_SOURCE_FIELDS = (
    "companyId",
    "projectId",
    "estimateId",
    "sourceRevision",
    "reconciliationId",
    "baseEstimateId",
    "reconciliationStatus",
)
_READINESS_SOURCE_FIELDS = frozenset({
    "companyId",
    "projectId",
    "estimateId",
    "sourceRevision",
    "reconciliationId",
    "baseEstimateId",
    "impactEvidenceSha256",
})
_CANDIDATE_FIELDS = frozenset({
    "subjectKind",
    "subjectId",
    "anomalyCode",
    "recommendationCode",
})
_CONTENT_RESULT_FIELDS = frozenset({
    "warehouseAnomalyContentVersion",
    "ok",
    "dryRun",
    "writesAttempted",
    "previewOnly",
    "stockMovementAllowed",
    "inventoryAdjustmentAllowed",
    "applyAllowed",
    "state",
    "source",
    "candidate",
    "content",
    "blockers",
    "contentSha256",
    "readOnlyTransaction",
    "rolledBack",
})
_CONTENT_SOURCE_FIELDS = frozenset(_STORED_SOURCE_FIELDS) | frozenset({
    "revalidatedRelevantEvidenceSha256",
})
_CONTENT_FIELDS = frozenset({"title", "finding", "nextSafeAction"})
_CONTENT_BLOCKERS = MappingProxyType({
    "blocked": frozenset({
        "warehouse_anomaly_current_source_not_ready",
        "warehouse_anomaly_current_snapshot_blocked",
    }),
    "stale": frozenset({
        "warehouse_anomaly_source_drift",
        "warehouse_anomaly_candidate_stale",
        "warehouse_anomaly_relevant_evidence_drift",
    }),
})
_READINESS_FIELDS = frozenset({
    "warehouseAnomalyReadinessVersion",
    "ok",
    "dryRun",
    "writesAttempted",
    "previewOnly",
    "stockMovementAllowed",
    "inventoryAdjustmentAllowed",
    "applyAllowed",
    "state",
    "source",
    "classificationComplete",
    "readyForRecommendationPreview",
    "candidateCount",
    "candidates",
    "blockers",
})
_READINESS_BLOCKERS = frozenset({
    "warehouse_anomaly_schema_not_ready",
    "warehouse_anomaly_scan_incomplete",
    "warehouse_anomaly_facts_truncated",
    "warehouse_anomaly_reviews_truncated",
    "warehouse_anomaly_subject_invalid",
    "warehouse_anomaly_duplicate_candidate",
    "warehouse_anomaly_source_items_limit_exceeded",
    "warehouse_anomaly_reason_unsupported",
    "warehouse_anomaly_systemic_source_incomplete",
    "warehouse_anomaly_supply_not_ready",
})
_CURRENT_WRAPPER_FIELDS = frozenset({
    "reportVersion",
    "ok",
    "dryRun",
    "writesAttempted",
    "schemaReady",
    "missingColumns",
    "scanComplete",
    "sourceReady",
    "readyForDomainScan",
    "source",
    "summary",
    "issueCount",
    "reasonCounts",
    "issues",
    "issuesTruncated",
    "readyForSupplyWarehouseProjection",
    "supplyWarehouseImpact",
})
_CURRENT_SUMMARY_FIELDS = frozenset({
    "estimateRows",
    "reconciliationRows",
})
_CURRENT_ISSUE_FIELDS = frozenset({
    "reasonCode",
    "companyId",
    "projectId",
    "estimateId",
})
_CURRENT_CORE_SOURCE_FIELDS = frozenset({
    "companyId",
    "projectId",
    "estimateId",
    "sourceRevision",
})
_CURRENT_READY_SOURCE_FIELDS = frozenset(_STORED_SOURCE_FIELDS)
_RAW_PROJECTION_FIELDS = frozenset({
    "state",
    "schemaReady",
    "missingColumns",
    "scanComplete",
    "complete",
    "summary",
    "openSupply",
    "protectedEvidence",
    "factsTruncated",
    "reasonCounts",
    "needsReview",
    "needsReviewTruncated",
})
_RAW_SUMMARY_FIELDS = frozenset({
    "supplyRequestRows",
    "supplyItems",
    "openSupplyItems",
    "protectedSupplyItems",
    "closedSupplyRequests",
    "deliveries",
    "allocations",
    "supplierInvoices",
    "warehouseInvoices",
    "warehouseHistoryRows",
    "receiptLots",
    "warehouseMovements",
    "lotMovements",
    "needsReview",
})
_RAW_EVIDENCE_FIELDS = frozenset({
    "closedSupplyRequestIds",
    "deliveryIds",
    "allocationIds",
    "supplierInvoiceIds",
    "warehouseInvoiceIds",
    "warehouseHistoryIds",
    "receiptLotIds",
    "warehouseMovementIds",
    "lotMovementIds",
})
_RAW_OPEN_SUPPLY_FIELDS = frozenset({
    "requestId",
    "requestItemIndex",
    "sourceEstimateId",
    "sourceSectionIndex",
    "sourceItemIndex",
    "state",
})
_RAW_REVIEW_FIELDS = frozenset({
    "sourceKind",
    "sourceId",
    "reasonCode",
})
_RECONCILIATION_STATUSES = frozenset({
    "Черновик",
    "На проверке",
    "Утверждена",
    "Отклонена",
})
_SCHEMA_SCAN_LIMIT_EXCEEDED = "schema_scan_limit_exceeded"
_BASELINE_REQUIRED_COLUMNS = frozenset("""
estimate_reconciliations.base_estimate_id
estimate_reconciliations.id
estimate_reconciliations.next_estimate_id
estimate_reconciliations.smeta_type
estimate_reconciliations.status
estimate_reconciliations.work_package
estimates.company_id
estimates.id
estimates.is_template
estimates.project_id
estimates.sections_json
estimates.smeta_type
estimates.status
estimates.version
estimates.work_package
projects.company_id
projects.id
""".split())
_RAW_REQUIRED_COLUMNS = frozenset("""
estimate_row_supply_allocations.allocation_quantity
estimate_row_supply_allocations.company_id
estimate_row_supply_allocations.id
estimate_row_supply_allocations.request_id
estimate_row_supply_allocations.request_item_index
estimate_row_supply_allocations.source_estimate_id
estimate_row_supply_allocations.source_item_index
estimate_row_supply_allocations.source_section_index
estimates.company_id
estimates.id
estimates.project_id
estimates.sections_json
estimates.work_package
projects.company_id
projects.id
projects.name
supplier_invoices.company_id
supplier_invoices.id
supplier_invoices.request_id
supply_deliveries.company_id
supply_deliveries.id
supply_deliveries.material_name
supply_deliveries.project
supply_deliveries.received_quantity
supply_deliveries.request_id
supply_deliveries.unit
supply_deliveries.work_package
supply_requests.company_id
supply_requests.id
supply_requests.items_json
supply_requests.project
supply_requests.status
supply_requests.work_package
warehouse_history.company_id
warehouse_history.id
warehouse_history.source_invoice_id
warehouse_history.source_invoice_line_index
warehouse_history.work_package
warehouse_invoices.company_id
warehouse_invoices.id
warehouse_invoices.items
warehouse_invoices.project
warehouse_invoices.supplier_invoice_id
warehouse_invoices.supply_delivery_id
warehouse_invoices.supply_request_id
warehouse_lot_movements.company_id
warehouse_lot_movements.id
warehouse_lot_movements.lot_id
warehouse_lot_movements.warehouse_movement_id
warehouse_movements.company_id
warehouse_movements.id
warehouse_movements.source_invoice_id
warehouse_movements.source_invoice_line_index
warehouse_movements.work_package
warehouse_receipt_lots.company_id
warehouse_receipt_lots.id
warehouse_receipt_lots.invoice_line_index
warehouse_receipt_lots.project_id
warehouse_receipt_lots.warehouse_invoice_id
""".split())

_BASELINE_REASON_RULES = MappingProxyType({
    "estimate_revision_impact_schema_not_ready": (False, False, 0, 0, 0, 0),
    "impact_source_not_found": (True, True, 0, 0, 0, 0),
    "impact_source_ambiguous": (True, True, 2, 2, 0, 0),
    "impact_source_owner_mismatch": (True, True, 1, 1, 0, 0),
    "impact_estimate_not_active": (True, True, 1, 1, 0, 0),
    "impact_estimate_template": (True, True, 1, 1, 0, 0),
    "impact_estimate_not_customer": (True, True, 1, 1, 0, 0),
    "impact_estimate_package_invalid": (True, True, 1, 1, 0, 0),
    "impact_estimate_snapshot_invalid": (True, True, 1, 1, 0, 0),
    "impact_estimate_snapshot_too_large": (True, True, 1, 1, 0, 0),
    "source_revision_mismatch": (True, True, 1, 1, 0, 0),
    "impact_reconciliation_scan_limit_exceeded": (
        True, False, 1, 1, 101, 101,
    ),
    "impact_reconciliation_not_found": (True, True, 1, 1, 0, 0),
    "impact_reconciliation_ambiguous": (True, True, 1, 1, 2, 100),
    "impact_reconciliation_id_invalid": (True, True, 1, 1, 1, 1),
    "impact_reconciliation_estimate_pair_invalid": (
        True, True, 1, 1, 1, 1,
    ),
    "impact_reconciliation_owner_mismatch": (True, True, 1, 1, 1, 1),
    "impact_reconciliation_not_customer": (True, True, 1, 1, 1, 1),
    "impact_reconciliation_package_mismatch": (True, True, 1, 1, 1, 1),
    "impact_reconciliation_next_not_active": (True, True, 1, 1, 1, 1),
    "impact_reconciliation_status_invalid": (True, True, 1, 1, 1, 1),
})

_ID_NONE = "none"
_ID_POSITIVE = "positive"
_ID_OPTIONAL = "optional"
_RAW_REVIEW_RULES = MappingProxyType({
    "supply_warehouse_impact_schema_not_ready": ("supplyWarehouse", _ID_NONE),
    "supply_warehouse_project_identity_invalid": ("supplyWarehouse", _ID_NONE),
    "supply_warehouse_source_snapshot_invalid": ("supplyWarehouse", _ID_NONE),
    "supply_request_scan_limit_exceeded": ("supplyWarehouse", _ID_NONE),
    "supply_warehouse_scan_limit_exceeded": ("supplyWarehouse", _ID_NONE),
    "supply_request_identity_invalid": ("supply", _ID_NONE),
    "supply_request_owner_mismatch": ("supply", _ID_NONE),
    "supply_source_coordinate_not_found": ("supply", _ID_POSITIVE),
    "supply_source_snapshot_invalid": ("supply", _ID_POSITIVE),
    "supply_source_item_key_invalid": ("supply", _ID_POSITIVE),
    "supply_source_item_key_ambiguous": ("supply", _ID_POSITIVE),
    "supply_request_project_mismatch": ("supply", _ID_POSITIVE),
    "supply_request_package_mismatch": ("supply", _ID_POSITIVE),
    "supply_items_json_invalid": ("supply", _ID_POSITIVE),
    "supply_request_item_limit_exceeded": ("supply", _ID_POSITIVE),
    "supply_source_lineage_invalid": ("supply", _ID_POSITIVE),
    "supply_source_coordinate_invalid": ("supply", _ID_POSITIVE),
    "supply_source_lineage_drift": ("supply", _ID_POSITIVE),
    "supply_quantity_invalid": ("supply", _ID_POSITIVE),
    "supply_source_coordinate_duplicate": ("supply", _ID_POSITIVE),
    "supply_source_estimate_invalid": ("supply", _ID_POSITIVE),
    "supply_snapshot_content_invalid": ("supply", _ID_POSITIVE),
    "supply_source_item_key_noncanonical": ("supply", _ID_POSITIVE),
    "supply_source_item_key_missing": ("supply", _ID_POSITIVE),
    "supply_source_item_key_required": ("supply", _ID_POSITIVE),
    "supply_source_item_key_mismatch": ("supply", _ID_POSITIVE),
    "supply_delivery_allocation_ambiguous": ("supply", _ID_POSITIVE),
    "supply_allocation_lineage_drift": ("supply", _ID_POSITIVE),
    "supply_protected_exceeds_requested": ("supply", _ID_POSITIVE),
    "supply_delivery_identity_invalid": ("delivery", _ID_OPTIONAL),
    "supply_delivery_owner_mismatch": ("delivery", _ID_NONE),
    "supply_delivery_request_mismatch": ("delivery", _ID_POSITIVE),
    "supply_delivery_scope_mismatch": ("delivery", _ID_POSITIVE),
    "supply_received_quantity_invalid": ("delivery", _ID_POSITIVE),
    "supply_allocation_identity_invalid": ("allocation", _ID_OPTIONAL),
    "supply_allocation_owner_mismatch": ("allocation", _ID_NONE),
    "supply_allocation_request_mismatch": ("allocation", _ID_POSITIVE),
    "supply_allocation_lineage_invalid": ("allocation", _ID_POSITIVE),
    "supply_allocation_quantity_invalid": ("allocation", _ID_POSITIVE),
    "supplier_invoice_identity_invalid": ("supplier_invoice", _ID_OPTIONAL),
    "supplier_invoice_owner_mismatch": ("supplier_invoice", _ID_NONE),
    "supplier_invoice_request_mismatch": ("supplier_invoice", _ID_POSITIVE),
    "warehouse_invoice_identity_invalid": ("warehouseInvoice", _ID_OPTIONAL),
    "warehouse_invoice_owner_mismatch": ("warehouseInvoice", _ID_NONE),
    "warehouse_invoice_request_mismatch": ("warehouseInvoice", _ID_POSITIVE),
    "warehouse_invoice_project_mismatch": ("warehouseInvoice", _ID_POSITIVE),
    "warehouse_invoice_delivery_mismatch": ("warehouseInvoice", _ID_POSITIVE),
    "warehouse_invoice_supplier_invoice_mismatch": (
        "warehouseInvoice", _ID_POSITIVE,
    ),
    "warehouse_invoice_items_invalid": ("warehouseInvoice", _ID_POSITIVE),
    "warehouse_invoice_items_limit_exceeded": (
        "warehouseInvoice", _ID_POSITIVE,
    ),
    "warehouse_receipt_identity_invalid": ("warehouse_receipt", _ID_OPTIONAL),
    "warehouse_receipt_owner_mismatch": ("warehouse_receipt", _ID_NONE),
    "warehouse_receipt_invoice_mismatch": ("warehouse_receipt", _ID_POSITIVE),
    "warehouse_receipt_line_invalid": ("warehouse_receipt", _ID_POSITIVE),
    "warehouse_receipt_package_mismatch": ("warehouse_receipt", _ID_POSITIVE),
    "warehouse_receipt_lot_identity_invalid": (
        "warehouse_receipt_lot", _ID_OPTIONAL,
    ),
    "warehouse_receipt_lot_owner_mismatch": (
        "warehouse_receipt_lot", _ID_NONE,
    ),
    "warehouse_receipt_lot_invoice_mismatch": (
        "warehouse_receipt_lot", _ID_POSITIVE,
    ),
    "warehouse_receipt_lot_line_invalid": (
        "warehouse_receipt_lot", _ID_POSITIVE,
    ),
    "warehouse_receipt_lot_project_mismatch": (
        "warehouse_receipt_lot", _ID_POSITIVE,
    ),
    "warehouse_movement_identity_invalid": (
        "warehouse_movement", _ID_OPTIONAL,
    ),
    "warehouse_movement_owner_mismatch": ("warehouse_movement", _ID_NONE),
    "warehouse_movement_invoice_mismatch": (
        "warehouse_movement", _ID_POSITIVE,
    ),
    "warehouse_movement_line_invalid": (
        "warehouse_movement", _ID_POSITIVE,
    ),
    "warehouse_movement_package_mismatch": (
        "warehouse_movement", _ID_POSITIVE,
    ),
    "warehouse_lot_movement_identity_invalid": ("lotMovement", _ID_OPTIONAL),
    "warehouse_lot_movement_owner_mismatch": ("lotMovement", _ID_NONE),
    "warehouse_lot_movement_parent_mismatch": ("lotMovement", _ID_POSITIVE),
    "warehouse_lot_movement_source_mismatch": ("lotMovement", _ID_POSITIVE),
    "warehouse_movement_lot_missing": ("warehouseMovement", _ID_POSITIVE),
    "warehouse_lot_movement_missing": ("warehouseMovement", _ID_POSITIVE),
})
_RAW_SYSTEMIC_PROJECTION_RULES = MappingProxyType({
    "supply_warehouse_impact_schema_not_ready": (
        "incomplete", False, False,
    ),
    "supply_warehouse_project_identity_invalid": (
        "review_required", True, True,
    ),
    "supply_warehouse_source_snapshot_invalid": (
        "review_required", True, True,
    ),
    "supply_request_scan_limit_exceeded": (
        "incomplete", True, False,
    ),
    "supply_warehouse_scan_limit_exceeded": (
        "incomplete", True, False,
    ),
})

_RAW_COUNT_LIST_PAIRS = MappingProxyType({
    "openSupplyItems": "openSupply",
    "closedSupplyRequests": "closedSupplyRequestIds",
    "deliveries": "deliveryIds",
    "allocations": "allocationIds",
    "supplierInvoices": "supplierInvoiceIds",
    "warehouseInvoices": "warehouseInvoiceIds",
    "warehouseHistoryRows": "warehouseHistoryIds",
    "receiptLots": "receiptLotIds",
    "warehouseMovements": "warehouseMovementIds",
    "lotMovements": "lotMovementIds",
})
_MAX_CURRENT_SNAPSHOT_NODES = 20000
_MAX_RAW_REVIEWS = 10800
_MAX_READINESS_CANDIDATES = 100


class WarehouseAnomalyContentError(ValueError):
    """Fixed-code A9.2 error without report or business content."""

    def __init__(self, code):
        self.code = str(code)
        super().__init__(self.code)


@dataclass(frozen=True)
class _PreparedWarehouseAnomalyContent:
    __slots__ = (
        "source_contract",
        "stored_source",
        "candidate",
        "impact_evidence_sha256",
        "relevant_evidence_sha256",
    )

    source_contract: EstimateRevisionSource
    stored_source: Mapping
    candidate: Mapping
    impact_evidence_sha256: str
    relevant_evidence_sha256: str


def _fail(code):
    raise WarehouseAnomalyContentError(code) from None


def _selection(value):
    if type(value) is not dict or set(value) != _SELECTION_FIELDS:
        _fail("warehouse_anomaly_content_selection_invalid")
    subject_kind = value.get("subjectKind")
    subject_id = value.get("subjectId")
    anomaly_code = value.get("anomalyCode")
    if (
        type(subject_kind) is not str
        or not subject_kind
        or type(subject_id) is not int
        or subject_id <= 0
        or type(anomaly_code) is not str
        or not anomaly_code
        or _SELECTION_RULES.get(anomaly_code) != subject_kind
    ):
        _fail("warehouse_anomaly_content_selection_invalid")
    return {
        "subjectKind": subject_kind,
        "subjectId": subject_id,
        "anomalyCode": anomaly_code,
    }


def _json_native_snapshot(value, *, max_nodes=None):
    active = set()
    memo = {}
    visited_nodes = 0

    def copy_value(item):
        nonlocal visited_nodes
        visited_nodes += 1
        if max_nodes is not None and visited_nodes > max_nodes:
            raise ValueError("JSON value exceeds the node limit")
        item_type = type(item)
        if item_type is dict:
            identity = id(item)
            if identity in active:
                raise RecursionError("recursive JSON value")
            if identity in memo:
                return memo[identity]
            active.add(identity)
            copied = {}
            memo[identity] = copied
            try:
                for key, child in item.items():
                    if type(key) is not str:
                        raise TypeError("JSON object key is not a string")
                    copied[key] = copy_value(child)
                return copied
            finally:
                active.remove(identity)
        if item_type is list:
            identity = id(item)
            if identity in active:
                raise RecursionError("recursive JSON value")
            if identity in memo:
                return memo[identity]
            active.add(identity)
            copied = []
            memo[identity] = copied
            try:
                copied.extend(copy_value(child) for child in item)
                return copied
            finally:
                active.remove(identity)
        if item_type in (str, int, bool) or item is None:
            return item
        if item_type is float and math.isfinite(item):
            return item
        raise TypeError("value is not an exact JSON-native value")

    return copy_value(value)


def _canonical_chunks(value):
    encoder = json.JSONEncoder(
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    for chunk in encoder.iterencode(value):
        yield chunk.encode("utf-8")


def _snapshot_stored_report(value):
    try:
        snapshot = _json_native_snapshot(value)
        if type(snapshot) is not dict:
            _fail("warehouse_anomaly_content_input_invalid")
        size = 0
        for chunk in _canonical_chunks(snapshot):
            size += len(chunk)
            if size > _MAX_STORED_REPORT_CANONICAL_BYTES:
                _fail("warehouse_anomaly_content_input_invalid")
        return snapshot
    except WarehouseAnomalyContentError:
        raise
    except (
        TypeError,
        ValueError,
        RecursionError,
        UnicodeError,
        OverflowError,
    ):
        _fail("warehouse_anomaly_content_input_invalid")


def _canonical_sha256(value):
    digest = hashlib.sha256()
    for chunk in _canonical_chunks(value):
        digest.update(chunk)
    return digest.hexdigest()


def _calculate_relevant_evidence_sha256(report):
    return _canonical_sha256({
        "warehouseAnomalyRelevantEvidenceVersion": (
            _RELEVANT_EVIDENCE_VERSION
        ),
        "source": report["source"],
        "supply": report["domains"]["supply"],
        "warehouse": report["domains"]["warehouse"],
    })


def _validated_readiness(value):
    if type(value) is not dict or set(value) != _READINESS_FIELDS:
        _fail("warehouse_anomaly_content_contract_invalid")
    source = value.get("source")
    candidates = value.get("candidates")
    blockers = value.get("blockers")
    candidate_count = value.get("candidateCount")
    state = value.get("state")
    if (
        value.get("warehouseAnomalyReadinessVersion")
        != WAREHOUSE_ANOMALY_READINESS_VERSION
        or type(value.get("warehouseAnomalyReadinessVersion")) is not int
        or value.get("ok") is not True
        or value.get("dryRun") is not True
        or type(value.get("writesAttempted")) is not int
        or value.get("writesAttempted") != 0
        or value.get("previewOnly") is not True
        or value.get("stockMovementAllowed") is not False
        or value.get("inventoryAdjustmentAllowed") is not False
        or value.get("applyAllowed") is not False
        or type(value.get("classificationComplete")) is not bool
        or type(value.get("readyForRecommendationPreview")) is not bool
        or type(state) is not str
        or state not in {"ready", "clear", "blocked"}
        or type(source) is not dict
        or set(source) != _READINESS_SOURCE_FIELDS
        or type(candidates) is not list
        or type(candidate_count) is not int
        or candidate_count < 0
        or candidate_count > _MAX_READINESS_CANDIDATES
        or candidate_count != len(candidates)
        or type(blockers) is not list
        or len(blockers) > len(_READINESS_BLOCKERS)
        or any(
            type(blocker) is not str
            or len(blocker) > max(map(len, _READINESS_BLOCKERS))
            or blocker not in _READINESS_BLOCKERS
            for blocker in blockers
        )
        or blockers != sorted(set(blockers))
    ):
        _fail("warehouse_anomaly_content_contract_invalid")
    if (
        any(
            type(source.get(name)) is not int or source[name] <= 0
            for name in (
                "companyId", "projectId", "estimateId",
                "reconciliationId", "baseEstimateId",
            )
        )
        or source["baseEstimateId"] == source["estimateId"]
        or type(source.get("sourceRevision")) is not str
        or not source["sourceRevision"].startswith("sha256:")
        or not _lowercase_sha256(source["sourceRevision"][len("sha256:"):])
        or not _lowercase_sha256(source.get("impactEvidenceSha256"))
    ):
        _fail("warehouse_anomaly_content_contract_invalid")
    candidate_keys = []
    for candidate in candidates:
        if (
            type(candidate) is not dict
            or set(candidate) != _CANDIDATE_FIELDS
            or type(candidate.get("subjectKind")) is not str
            or type(candidate.get("subjectId")) is not int
            or candidate["subjectId"] <= 0
            or type(candidate.get("anomalyCode")) is not str
            or type(candidate.get("recommendationCode")) is not str
            or _SELECTION_RULES.get(candidate["anomalyCode"])
            != candidate["subjectKind"]
            or _ANOMALY_RECOMMENDATION_RULES.get(
                candidate["anomalyCode"]
            ) != candidate["recommendationCode"]
        ):
            _fail("warehouse_anomaly_content_contract_invalid")
        candidate_keys.append((
            candidate["subjectKind"],
            candidate["subjectId"],
            candidate["anomalyCode"],
        ))
    if (
        candidate_keys != sorted(candidate_keys)
        or len(candidate_keys) != len(set(candidate_keys))
    ):
        _fail("warehouse_anomaly_content_contract_invalid")
    expected_ready = state == "ready"
    expected_complete = state != "blocked"
    if (
        value["readyForRecommendationPreview"] is not expected_ready
        or value["classificationComplete"] is not expected_complete
        or (expected_ready and (not candidates or blockers))
        or (not expected_ready and candidates)
        or (state == "clear" and blockers)
        or (state == "blocked" and not blockers)
    ):
        _fail("warehouse_anomaly_content_contract_invalid")
    return value


def _source_contract(source):
    try:
        return validate_estimate_revision_source({
            "schemaVersion": REPORT_VERSION,
            "eventType": EVENT_TYPE,
            "companyId": source["companyId"],
            "projectId": source["projectId"],
            "estimateId": source["estimateId"],
            "sourceRevision": source["sourceRevision"],
        })
    except (EstimateRevisionImpactContractError, KeyError, TypeError):
        _fail("warehouse_anomaly_content_contract_invalid")


def _stored_source(snapshot, readiness_source):
    source = snapshot.get("source")
    if type(source) is not dict or set(source) != set(_STORED_SOURCE_FIELDS):
        _fail("warehouse_anomaly_content_contract_invalid")
    expected = {
        name: source[name]
        for name in _STORED_SOURCE_FIELDS
        if name != "reconciliationStatus"
    }
    actual = {
        name: readiness_source.get(name)
        for name in expected
    }
    if (
        expected != actual
        or readiness_source.get("impactEvidenceSha256")
        != snapshot.get("evidenceSha256")
    ):
        _fail("warehouse_anomaly_content_contract_invalid")
    return dict(source)


def _matching_candidate(readiness, selection):
    matches = [
        candidate
        for candidate in readiness["candidates"]
        if all(candidate[name] == selection[name] for name in _SELECTION_FIELDS)
    ]
    if len(matches) != 1:
        _fail("warehouse_anomaly_content_selection_invalid")
    return dict(matches[0])


def _exact_dict(value, fields):
    if type(value) is not dict or len(value) != len(fields):
        raise ValueError("mapping fields are invalid")
    max_key_length = max(map(len, fields))
    if any(
        type(key) is not str or len(key) > max_key_length
        for key in value
    ) or set(value) != set(fields):
        raise ValueError("mapping fields are invalid")
    return value


def _exact_bool(value):
    if type(value) is not bool:
        raise ValueError("boolean is invalid")
    return value


def _bounded_int(value, minimum, maximum):
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError("integer is invalid")
    return value


def _positive_current_int(value):
    if type(value) is not int or value <= 0:
        raise ValueError("positive integer is invalid")
    return value


def _non_negative_current_int(value):
    if type(value) is not int or value < 0:
        raise ValueError("non-negative integer is invalid")
    return value


def _validated_missing_columns(value, allowlist):
    if type(value) is not list or len(value) > len(allowlist):
        raise ValueError("missing columns are invalid")
    max_length = max(
        len(_SCHEMA_SCAN_LIMIT_EXCEEDED),
        max(map(len, allowlist)),
    )
    if any(
        type(item) is not str or len(item) > max_length
        for item in value
    ):
        raise ValueError("missing columns are invalid")
    if value == [_SCHEMA_SCAN_LIMIT_EXCEEDED]:
        return list(value)
    if value != sorted(set(value)) or not set(value).issubset(allowlist):
        raise ValueError("missing columns are invalid")
    return list(value)


def _bounded_sorted_ids(value):
    if type(value) is not list or len(value) > 100:
        raise ValueError("ID list is invalid")
    ids = [_positive_current_int(item) for item in value]
    if ids != sorted(set(ids)):
        raise ValueError("ID list is invalid")
    return ids


def _validated_raw_review(value):
    review = _exact_dict(value, _RAW_REVIEW_FIELDS)
    reason = review["reasonCode"]
    kind = review["sourceKind"]
    max_reason_length = max(map(len, _RAW_REVIEW_RULES))
    max_kind_length = max(
        len(rule[0]) for rule in _RAW_REVIEW_RULES.values()
    )
    if (
        type(reason) is not str
        or len(reason) > max_reason_length
        or reason not in _RAW_REVIEW_RULES
        or type(kind) is not str
        or len(kind) > max_kind_length
    ):
        raise ValueError("review is invalid")
    expected_kind, id_policy = _RAW_REVIEW_RULES[reason]
    source_id = review["sourceId"]
    if kind != expected_kind:
        raise ValueError("review is invalid")
    if id_policy == _ID_NONE:
        valid_id = source_id is None
    elif id_policy == _ID_POSITIVE:
        valid_id = type(source_id) is int and source_id > 0
    else:
        valid_id = source_id is None or (
            type(source_id) is int and source_id > 0
        )
    if not valid_id:
        raise ValueError("review is invalid")
    return review


def _validated_open_supply(value, base_estimate_id, expected_count):
    if type(value) is not list or len(value) > 100:
        raise ValueError("open supply is invalid")
    if len(value) != min(expected_count, 100):
        raise ValueError("open supply count is invalid")
    keys = []
    source_coordinates = []
    for raw in value:
        item = _exact_dict(raw, _RAW_OPEN_SUPPLY_FIELDS)
        request_id = _positive_current_int(item["requestId"])
        request_item_index = _bounded_int(item["requestItemIndex"], 0, 99)
        source_estimate_id = _positive_current_int(item["sourceEstimateId"])
        section_index = _non_negative_current_int(
            item["sourceSectionIndex"]
        )
        source_item_index = _non_negative_current_int(
            item["sourceItemIndex"]
        )
        if (
            item["state"] != "open_balance"
            or type(item["state"]) is not str
            or source_estimate_id != base_estimate_id
        ):
            raise ValueError("open supply is invalid")
        keys.append((
            request_id,
            request_item_index,
            section_index,
            source_item_index,
        ))
        source_coordinates.append((
            request_id,
            section_index,
            source_item_index,
        ))
    if (
        keys != sorted(keys)
        or len(set(keys)) != len(keys)
        or len(set(source_coordinates)) != len(source_coordinates)
    ):
        raise ValueError("open supply order is invalid")
    return value


def _is_canonical_not_collected(projection):
    return bool(
        projection["state"] == "not_collected"
        and projection["schemaReady"] is True
        and projection["missingColumns"] == []
        and projection["scanComplete"] is False
        and projection["complete"] is False
        and all(value == 0 for value in projection["summary"].values())
        and projection["openSupply"] == []
        and all(
            value == []
            for value in projection["protectedEvidence"].values()
        )
        and projection["factsTruncated"] is False
        and projection["reasonCounts"] == {}
        and projection["needsReview"] == []
        and projection["needsReviewTruncated"] is False
    )


def _validate_raw_supply_warehouse_projection(
    value,
    *,
    base_estimate_id,
    allow_not_collected,
):
    projection = _exact_dict(value, _RAW_PROJECTION_FIELDS)
    state = projection["state"]
    if (
        type(state) is not str
        or len(state) > len("review_required")
        or state not in {
            "complete", "incomplete", "review_required", "not_collected",
        }
    ):
        raise ValueError("projection state is invalid")
    schema_ready = _exact_bool(projection["schemaReady"])
    scan_complete = _exact_bool(projection["scanComplete"])
    complete = _exact_bool(projection["complete"])
    facts_truncated = _exact_bool(projection["factsTruncated"])
    reviews_truncated = _exact_bool(projection["needsReviewTruncated"])
    missing = _validated_missing_columns(
        projection["missingColumns"], _RAW_REQUIRED_COLUMNS,
    )
    if schema_ready is not (missing == []):
        raise ValueError("projection schema flags are invalid")

    summary = _exact_dict(projection["summary"], _RAW_SUMMARY_FIELDS)
    counts = {
        name: _bounded_int(summary[name], 0, _MAX_RAW_REVIEWS)
        for name in _RAW_SUMMARY_FIELDS
    }
    requests = counts["supplyRequestRows"]
    supply_items = counts["supplyItems"]
    open_items = counts["openSupplyItems"]
    protected_items = counts["protectedSupplyItems"]
    if (
        requests > 100
        or supply_items > min(10000, 100 * requests)
        or open_items > supply_items
        or protected_items > supply_items
        or open_items + protected_items > supply_items
        or counts["closedSupplyRequests"] > requests
        or any(
            counts[name] > 100
            for name in (
                "deliveries", "allocations", "supplierInvoices",
                "warehouseInvoices", "warehouseHistoryRows", "receiptLots",
                "warehouseMovements", "lotMovements",
            )
        )
    ):
        raise ValueError("projection counts are invalid")

    evidence = _exact_dict(
        projection["protectedEvidence"], _RAW_EVIDENCE_FIELDS,
    )
    validated_ids = {
        name: _bounded_sorted_ids(evidence[name])
        for name in _RAW_EVIDENCE_FIELDS
    }
    _validated_open_supply(
        projection["openSupply"], base_estimate_id, open_items,
    )
    for count_name, list_name in _RAW_COUNT_LIST_PAIRS.items():
        values = (
            projection["openSupply"]
            if list_name == "openSupply"
            else validated_ids[list_name]
        )
        if len(values) != min(counts[count_name], 100):
            raise ValueError("projection list count is invalid")
    expected_facts_truncated = any(
        counts[count_name] > 100
        for count_name in _RAW_COUNT_LIST_PAIRS
    )
    if facts_truncated is not expected_facts_truncated:
        raise ValueError("projection truncation is invalid")

    reason_counts = projection["reasonCounts"]
    if type(reason_counts) is not dict or len(reason_counts) > len(
        _RAW_REVIEW_RULES
    ):
        raise ValueError("projection reasons are invalid")
    max_reason_length = max(map(len, _RAW_REVIEW_RULES))
    normalized_reasons = {}
    for reason, count in reason_counts.items():
        if (
            type(reason) is not str
            or len(reason) > max_reason_length
            or reason not in _RAW_REVIEW_RULES
        ):
            raise ValueError("projection reasons are invalid")
        normalized_reasons[reason] = _bounded_int(
            count, 1, _MAX_RAW_REVIEWS,
        )
    review_count = counts["needsReview"]
    if sum(normalized_reasons.values()) != review_count:
        raise ValueError("projection reason count is invalid")
    reviews = projection["needsReview"]
    if type(reviews) is not list or len(reviews) > 100:
        raise ValueError("projection reviews are invalid")
    if len(reviews) != min(review_count, 100):
        raise ValueError("projection review count is invalid")
    for review in reviews:
        _validated_raw_review(review)
    visible = Counter(review["reasonCode"] for review in reviews)
    if reviews_truncated is not (review_count > 100):
        raise ValueError("projection review truncation is invalid")
    if reviews_truncated:
        if (
            not set(visible).issubset(normalized_reasons)
            or any(
                visible[reason] > normalized_reasons[reason]
                for reason in visible
            )
        ):
            raise ValueError("projection review histogram is invalid")
    elif dict(sorted(visible.items())) != dict(sorted(
        normalized_reasons.items()
    )):
        raise ValueError("projection review histogram is invalid")

    if state == "not_collected":
        if not allow_not_collected or not _is_canonical_not_collected(
            projection
        ):
            raise ValueError("not-collected projection is invalid")
        return projection

    systemic_reasons = set(normalized_reasons).intersection(
        _RAW_SYSTEMIC_PROJECTION_RULES
    )
    if systemic_reasons:
        if len(systemic_reasons) != 1 or len(normalized_reasons) != 1:
            raise ValueError("systemic projection is invalid")
        reason = next(iter(systemic_reasons))
        expected_state, expected_schema, expected_scan = (
            _RAW_SYSTEMIC_PROJECTION_RULES[reason]
        )
        expected_review = {
            "sourceKind": "supplyWarehouse",
            "sourceId": None,
            "reasonCode": reason,
        }
        if (
            state != expected_state
            or schema_ready is not expected_schema
            or scan_complete is not expected_scan
            or complete is not False
            or facts_truncated is not False
            or reviews_truncated is not False
            or any(
                count != (1 if name == "needsReview" else 0)
                for name, count in counts.items()
            )
            or projection["openSupply"] != []
            or any(values for values in validated_ids.values())
            or normalized_reasons != {reason: 1}
            or reviews != [expected_review]
        ):
            raise ValueError("systemic projection is invalid")
        return projection

    if not schema_ready or not scan_complete:
        raise ValueError("projection incompleteness is invalid")

    expected_complete = bool(
        schema_ready
        and scan_complete
        and not facts_truncated
        and review_count == 0
    )
    expected_state = "complete" if expected_complete else (
        "incomplete"
        if not schema_ready or not scan_complete or facts_truncated
        else "review_required"
    )
    if complete is not expected_complete or state != expected_state:
        raise ValueError("projection state is inconsistent")
    return projection


def _expected_current_core(source_contract):
    if type(source_contract) is not EstimateRevisionSource:
        raise ValueError("source contract is invalid")
    validated = validate_estimate_revision_source({
        "schemaVersion": source_contract.schema_version,
        "eventType": source_contract.event_type,
        "companyId": source_contract.company_id,
        "projectId": source_contract.project_id,
        "estimateId": source_contract.estimate_id,
        "sourceRevision": source_contract.source_revision,
    })
    if validated != source_contract:
        raise ValueError("source contract is invalid")
    return {
        "companyId": source_contract.company_id,
        "projectId": source_contract.project_id,
        "estimateId": source_contract.estimate_id,
        "sourceRevision": source_contract.source_revision,
    }


def _validate_current_core_values(source):
    for name in ("companyId", "projectId", "estimateId"):
        _positive_current_int(source[name])
    revision = source["sourceRevision"]
    if (
        type(revision) is not str
        or len(revision) != len("sha256:") + 64
    ):
        raise ValueError("current source is invalid")


def _validate_nonready_baseline(report, expected_core, summary, missing):
    source = _exact_dict(report["source"], _CURRENT_CORE_SOURCE_FIELDS)
    _validate_current_core_values(source)
    if source != expected_core:
        raise ValueError("current source drifted")
    if report["issueCount"] != 1 or report["issuesTruncated"] is not False:
        raise ValueError("baseline issue count is invalid")
    reasons = report["reasonCounts"]
    if type(reasons) is not dict or len(reasons) != 1:
        raise ValueError("baseline reasons are invalid")
    reason = next(iter(reasons), None)
    if (
        type(reason) is not str
        or len(reason) > max(map(len, _BASELINE_REASON_RULES))
        or reason not in _BASELINE_REASON_RULES
        or reasons[reason] != 1
        or type(reasons[reason]) is not int
    ):
        raise ValueError("baseline reasons are invalid")
    issues = report["issues"]
    if type(issues) is not list or len(issues) != 1:
        raise ValueError("baseline issues are invalid")
    issue = _exact_dict(issues[0], _CURRENT_ISSUE_FIELDS)
    for name in ("companyId", "projectId", "estimateId"):
        _positive_current_int(issue[name])
    if issue != {"reasonCode": reason, **{
        name: expected_core[name]
        for name in ("companyId", "projectId", "estimateId")
    }}:
        raise ValueError("baseline issue is invalid")
    (
        expected_schema,
        expected_scan,
        estimate_min,
        estimate_max,
        reconciliation_min,
        reconciliation_max,
    ) = _BASELINE_REASON_RULES[reason]
    if (
        report["schemaReady"] is not expected_schema
        or report["scanComplete"] is not expected_scan
        or (reason == "estimate_revision_impact_schema_not_ready")
        is not bool(missing)
        or not estimate_min <= summary["estimateRows"] <= estimate_max
        or not reconciliation_min
        <= summary["reconciliationRows"]
        <= reconciliation_max
    ):
        raise ValueError("baseline failure shape is invalid")


def _validate_current_snapshot(report, source_contract):
    expected_core = _expected_current_core(source_contract)
    current = _exact_dict(report, _CURRENT_WRAPPER_FIELDS)
    if (
        type(current["reportVersion"]) is not int
        or current["reportVersion"] != REPORT_VERSION
        or current["ok"] is not True
        or current["dryRun"] is not True
        or type(current["writesAttempted"]) is not int
        or current["writesAttempted"] != 0
    ):
        raise ValueError("current wrapper flags are invalid")
    for field in (
        "schemaReady", "scanComplete", "sourceReady", "readyForDomainScan",
        "issuesTruncated", "readyForSupplyWarehouseProjection",
    ):
        _exact_bool(current[field])
    if current["sourceReady"] is not current["readyForDomainScan"]:
        raise ValueError("current source flags are inconsistent")
    missing = _validated_missing_columns(
        current["missingColumns"], _BASELINE_REQUIRED_COLUMNS,
    )
    if current["schemaReady"] is not (missing == []):
        raise ValueError("current schema flags are inconsistent")
    summary = _exact_dict(current["summary"], _CURRENT_SUMMARY_FIELDS)
    summary = {
        "estimateRows": _bounded_int(summary["estimateRows"], 0, 2),
        "reconciliationRows": _bounded_int(
            summary["reconciliationRows"], 0, 101,
        ),
    }
    issue_count = _bounded_int(current["issueCount"], 0, 1)
    if (
        type(current["reasonCounts"]) is not dict
        or len(current["reasonCounts"]) > 1
        or type(current["issues"]) is not list
        or len(current["issues"]) > 1
        or len(current["issues"]) != min(issue_count, 100)
        or current["issuesTruncated"] is not (issue_count > 100)
    ):
        raise ValueError("current issue envelope is invalid")

    source_ready = current["sourceReady"]
    if source_ready:
        source = _exact_dict(
            current["source"], _CURRENT_READY_SOURCE_FIELDS,
        )
        _validate_current_core_values(source)
        if any(source[name] != expected_core[name] for name in expected_core):
            raise ValueError("current source drifted")
        reconciliation_id = _positive_current_int(source["reconciliationId"])
        base_estimate_id = _positive_current_int(source["baseEstimateId"])
        status = source["reconciliationStatus"]
        if (
            base_estimate_id == expected_core["estimateId"]
            or type(status) is not str
            or len(status) > max(map(len, _RECONCILIATION_STATUSES))
            or status not in _RECONCILIATION_STATUSES
            or reconciliation_id <= 0
            or current["schemaReady"] is not True
            or current["scanComplete"] is not True
            or missing
            or summary != {"estimateRows": 1, "reconciliationRows": 1}
            or issue_count != 0
            or current["reasonCounts"] != {}
            or current["issues"] != []
            or current["issuesTruncated"] is not False
        ):
            raise ValueError("ready current source is invalid")
    else:
        base_estimate_id = None
        _validate_nonready_baseline(current, expected_core, summary, missing)

    projection = _validate_raw_supply_warehouse_projection(
        current["supplyWarehouseImpact"],
        base_estimate_id=base_estimate_id,
        allow_not_collected=not source_ready,
    )
    if (
        current["readyForSupplyWarehouseProjection"]
        is not projection["complete"]
        or (not source_ready and not _is_canonical_not_collected(projection))
    ):
        raise ValueError("projection readiness is inconsistent")
    return current


def _validate_current_warehouse_anomaly_report(report, source_contract):
    """Return a detached exact A7 wrapper or fail with one fixed code."""

    try:
        snapshot = _json_native_snapshot(
            report,
            max_nodes=_MAX_CURRENT_SNAPSHOT_NODES,
        )
        return _validate_current_snapshot(snapshot, source_contract)
    except MemoryError:
        raise
    except Exception:
        _fail("warehouse_anomaly_content_current_report_invalid")


def _prepare_warehouse_anomaly_content(combined_report, selected):
    """Return one detached immutable A9.2 plan after strict A9.1 preflight."""

    selection = _selection(selected)
    snapshot = _snapshot_stored_report(combined_report)
    try:
        readiness = build_warehouse_anomaly_readiness(snapshot)
    except MemoryError:
        raise
    except Exception:
        _fail("warehouse_anomaly_content_input_invalid")
    readiness = _validated_readiness(readiness)
    if readiness["readyForRecommendationPreview"] is not True:
        _fail("warehouse_anomaly_content_stored_readiness_blocked")

    candidate = _matching_candidate(readiness, selection)
    stored_source = _stored_source(snapshot, readiness["source"])
    source_contract = _source_contract(stored_source)

    try:
        if calculate_evidence_sha256(snapshot) != snapshot["evidenceSha256"]:
            _fail("warehouse_anomaly_content_contract_invalid")
        relevant_sha256 = _calculate_relevant_evidence_sha256(snapshot)
    except (
        KeyError,
        TypeError,
        ValueError,
        RecursionError,
        UnicodeError,
        OverflowError,
    ):
        _fail("warehouse_anomaly_content_contract_invalid")

    return _PreparedWarehouseAnomalyContent(
        source_contract=source_contract,
        stored_source=MappingProxyType(stored_source),
        candidate=MappingProxyType(candidate),
        impact_evidence_sha256=snapshot["evidenceSha256"],
        relevant_evidence_sha256=relevant_sha256,
    )


def _lowercase_sha256(value):
    return (
        type(value) is str
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _validated_prepared_content(prepared):
    try:
        if (
            type(prepared) is not _PreparedWarehouseAnomalyContent
            or type(prepared.source_contract) is not EstimateRevisionSource
            or type(prepared.stored_source) is not MappingProxyType
            or type(prepared.candidate) is not MappingProxyType
            or not _lowercase_sha256(prepared.impact_evidence_sha256)
            or not _lowercase_sha256(prepared.relevant_evidence_sha256)
        ):
            raise ValueError("prepared content is invalid")

        stored_source = _exact_dict(
            dict(prepared.stored_source), _CURRENT_READY_SOURCE_FIELDS,
        )
        expected_core = _expected_current_core(prepared.source_contract)
        _validate_current_core_values(stored_source)
        if any(
            stored_source[name] != expected_core[name]
            for name in expected_core
        ):
            raise ValueError("prepared source is invalid")
        _positive_current_int(stored_source["reconciliationId"])
        _positive_current_int(stored_source["baseEstimateId"])
        status = stored_source["reconciliationStatus"]
        if (
            stored_source["baseEstimateId"] == stored_source["estimateId"]
            or type(status) is not str
            or len(status) > max(map(len, _RECONCILIATION_STATUSES))
            or status not in _RECONCILIATION_STATUSES
        ):
            raise ValueError("prepared source is invalid")

        candidate = _exact_dict(
            dict(prepared.candidate), _CANDIDATE_FIELDS,
        )
        anomaly_code = candidate["anomalyCode"]
        recommendation_code = candidate["recommendationCode"]
        if (
            type(candidate["subjectKind"]) is not str
            or type(candidate["subjectId"]) is not int
            or candidate["subjectId"] <= 0
            or type(anomaly_code) is not str
            or type(recommendation_code) is not str
            or _SELECTION_RULES.get(anomaly_code)
            != candidate["subjectKind"]
            or _ANOMALY_RECOMMENDATION_RULES.get(anomaly_code)
            != recommendation_code
        ):
            raise ValueError("prepared candidate is invalid")
        return stored_source, candidate
    except MemoryError:
        raise
    except Exception:
        _fail("warehouse_anomaly_content_contract_invalid")


def _fixed_content(candidate):
    anomaly_code = candidate["anomalyCode"]
    recommendation_code = candidate["recommendationCode"]
    finding = _FIXED_FINDINGS.get(anomaly_code)
    recommendation = _FIXED_RECOMMENDATION_CONTENT.get(recommendation_code)
    if (
        _ANOMALY_RECOMMENDATION_RULES.get(anomaly_code)
        != recommendation_code
        or type(finding) is not str
        or type(recommendation) is not tuple
        or len(recommendation) != 2
        or any(type(value) is not str for value in recommendation)
    ):
        _fail("warehouse_anomaly_content_contract_invalid")
    title, next_safe_action = recommendation
    return {
        "title": title,
        "finding": finding,
        "nextSafeAction": next_safe_action,
    }


def _content_result(
    stored_source,
    candidate,
    *,
    state,
    blocker=None,
    relevant_sha256=None,
):
    ready = state == "preview_ready"
    if (
        ready is not (blocker is None)
        or ready is not (relevant_sha256 is not None)
        or state not in {"preview_ready", "blocked", "stale"}
        or (relevant_sha256 is not None and not _lowercase_sha256(
            relevant_sha256
        ))
    ):
        _fail("warehouse_anomaly_content_contract_invalid")

    public_source = dict(stored_source)
    public_source["revalidatedRelevantEvidenceSha256"] = (
        relevant_sha256 if ready else None
    )
    public_candidate = dict(candidate)
    content = _fixed_content(public_candidate) if ready else None
    result = {
        "warehouseAnomalyContentVersion": WAREHOUSE_ANOMALY_CONTENT_VERSION,
        "ok": True,
        "dryRun": True,
        "writesAttempted": 0,
        "previewOnly": True,
        "stockMovementAllowed": False,
        "inventoryAdjustmentAllowed": False,
        "applyAllowed": False,
        "state": state,
        "source": public_source,
        "candidate": public_candidate,
        "content": content,
        "blockers": [] if ready else [blocker],
        "contentSha256": None,
        "readOnlyTransaction": True,
        "rolledBack": True,
    }
    if ready:
        try:
            result["contentSha256"] = _canonical_sha256({
                "warehouseAnomalyContentVersion": (
                    WAREHOUSE_ANOMALY_CONTENT_VERSION
                ),
                "source": public_source,
                "candidate": public_candidate,
                "content": content,
            })
        except MemoryError:
            raise
        except Exception:
            _fail("warehouse_anomaly_content_contract_invalid")
    return result


def _current_combined_readiness(current):
    try:
        report = build_combined_report(
            current["source"],
            assignment=None,
            material=None,
            supply_warehouse=current["supplyWarehouseImpact"],
            economics=None,
        )
        report["readOnlyTransaction"] = True
        report["rolledBack"] = True
        readiness = _validated_readiness(
            build_warehouse_anomaly_readiness(report)
        )
        expected_source = {
            name: current["source"][name]
            for name in _STORED_SOURCE_FIELDS
            if name != "reconciliationStatus"
        }
        expected_source["impactEvidenceSha256"] = report["evidenceSha256"]
        if readiness["source"] != expected_source:
            raise ValueError("current readiness source is invalid")
        return report, readiness
    except MemoryError:
        raise
    except Exception:
        _fail("warehouse_anomaly_content_contract_invalid")


def _finalize_warehouse_anomaly_content(prepared, current_report):
    """Finalize one fixed A9.2 result from exact post-rollback evidence."""

    stored_source, candidate = _validated_prepared_content(prepared)
    current = _validate_current_warehouse_anomaly_report(
        current_report, prepared.source_contract,
    )
    if current["sourceReady"] is not True:
        return _content_result(
            stored_source,
            candidate,
            state="blocked",
            blocker="warehouse_anomaly_current_source_not_ready",
        )

    if any(
        current["source"][name] != stored_source[name]
        for name in (
            "reconciliationId", "baseEstimateId", "reconciliationStatus",
        )
    ):
        return _content_result(
            stored_source,
            candidate,
            state="stale",
            blocker="warehouse_anomaly_source_drift",
        )

    current_combined, readiness = _current_combined_readiness(current)
    if readiness["state"] == "blocked":
        return _content_result(
            stored_source,
            candidate,
            state="blocked",
            blocker="warehouse_anomaly_current_snapshot_blocked",
        )

    matches = [
        item for item in readiness["candidates"]
        if item == candidate
    ]
    if readiness["state"] != "ready" or len(matches) != 1:
        return _content_result(
            stored_source,
            candidate,
            state="stale",
            blocker="warehouse_anomaly_candidate_stale",
        )

    try:
        relevant_sha256 = _calculate_relevant_evidence_sha256(
            current_combined
        )
    except MemoryError:
        raise
    except Exception:
        _fail("warehouse_anomaly_content_contract_invalid")
    if relevant_sha256 != prepared.relevant_evidence_sha256:
        return _content_result(
            stored_source,
            candidate,
            state="stale",
            blocker="warehouse_anomaly_relevant_evidence_drift",
        )

    return _content_result(
        stored_source,
        candidate,
        state="preview_ready",
        relevant_sha256=relevant_sha256,
    )


def _validated_warehouse_anomaly_content_result(value, prepared):
    """Return one detached exact public result or fail with a fixed code."""

    try:
        stored_source, candidate = _validated_prepared_content(prepared)
        result = _json_native_snapshot(value, max_nodes=100)
        if type(result) is not dict or set(result) != _CONTENT_RESULT_FIELDS:
            raise ValueError("content result fields are invalid")
        state = result["state"]
        if (
            type(result["warehouseAnomalyContentVersion"]) is not int
            or result["warehouseAnomalyContentVersion"]
            != WAREHOUSE_ANOMALY_CONTENT_VERSION
            or result["ok"] is not True
            or result["dryRun"] is not True
            or type(result["writesAttempted"]) is not int
            or result["writesAttempted"] != 0
            or result["previewOnly"] is not True
            or result["stockMovementAllowed"] is not False
            or result["inventoryAdjustmentAllowed"] is not False
            or result["applyAllowed"] is not False
            or result["readOnlyTransaction"] is not True
            or result["rolledBack"] is not True
            or type(state) is not str
            or state not in {"preview_ready", "blocked", "stale"}
        ):
            raise ValueError("content result flags are invalid")

        source = _exact_dict(result["source"], _CONTENT_SOURCE_FIELDS)
        actual_candidate = _exact_dict(
            result["candidate"], _CANDIDATE_FIELDS,
        )
        if (
            any(
                type(source[name]) is not int or source[name] <= 0
                for name in (
                    "companyId", "projectId", "estimateId",
                    "reconciliationId", "baseEstimateId",
                )
            )
            or type(source["sourceRevision"]) is not str
            or type(source["reconciliationStatus"]) is not str
            or type(actual_candidate["subjectKind"]) is not str
            or type(actual_candidate["subjectId"]) is not int
            or actual_candidate["subjectId"] <= 0
            or type(actual_candidate["anomalyCode"]) is not str
            or type(actual_candidate["recommendationCode"]) is not str
            or actual_candidate != candidate
        ):
            raise ValueError("content candidate is invalid")
        blockers = result["blockers"]
        if type(blockers) is not list:
            raise ValueError("content blockers are invalid")

        if state == "preview_ready":
            relevant_sha256 = source[
                "revalidatedRelevantEvidenceSha256"
            ]
            expected_source = {
                **stored_source,
                "revalidatedRelevantEvidenceSha256": (
                    prepared.relevant_evidence_sha256
                ),
            }
            expected_content = _fixed_content(candidate)
            content = result["content"]
            content_sha256 = result["contentSha256"]
            if (
                source != expected_source
                or not _lowercase_sha256(relevant_sha256)
                or blockers != []
                or type(content) is not dict
                or set(content) != _CONTENT_FIELDS
                or content != expected_content
                or not _lowercase_sha256(content_sha256)
                or content_sha256 != _canonical_sha256({
                    "warehouseAnomalyContentVersion": (
                        WAREHOUSE_ANOMALY_CONTENT_VERSION
                    ),
                    "source": source,
                    "candidate": actual_candidate,
                    "content": content,
                })
            ):
                raise ValueError("ready content result is invalid")
        else:
            expected_source = {
                **stored_source,
                "revalidatedRelevantEvidenceSha256": None,
            }
            allowed_blockers = _CONTENT_BLOCKERS[state]
            if (
                source != expected_source
                or result["content"] is not None
                or result["contentSha256"] is not None
                or len(blockers) != 1
                or type(blockers[0]) is not str
                or blockers[0] not in allowed_blockers
            ):
                raise ValueError("non-ready content result is invalid")
        return result
    except MemoryError:
        raise
    except Exception:
        _fail("warehouse_anomaly_content_contract_invalid")
