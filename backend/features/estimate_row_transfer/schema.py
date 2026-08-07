"""Guarded additive schema migration for reviewed E4 transfer ledgers."""

import argparse
import hashlib
import json
import re

import psycopg2.extras


PLAN_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

PLAN_COLUMNS = {
    "id", "company_id", "project_id", "work_package", "smeta_type",
    "reconciliation_id", "base_estimate_id", "target_estimate_id",
    "target_estimate_version_id", "base_sections_sha256",
    "target_sections_sha256", "base_snapshot_row_count",
    "target_snapshot_row_count", "plan_sha256", "approved_plan_sha256",
    "status", "created_by_user_id", "created_by_name", "created_by_role",
    "approved_by_user_id", "approved_by_name", "approved_by_role",
    "approved_at", "created_at", "updated_at",
}
ENTRY_COLUMNS = {
    "id", "plan_id", "company_id", "project_id", "source_kind",
    "source_id", "source_parent_id", "request_item_index",
    "source_estimate_id", "source_estimate_version_id",
    "source_section_index", "source_item_index", "source_item_key",
    "source_sections_sha256", "target_estimate_id",
    "target_estimate_version_id", "target_section_index",
    "target_item_index", "target_item_key", "target_sections_sha256",
    "source_total_quantity", "source_protected_quantity",
    "source_available_quantity", "quantity", "created_at",
}
ASSIGNMENT_TRANSFER_COLUMNS = {
    "id", "entry_id", "plan_id", "company_id", "project_id",
    "reconciliation_id", "plan_sha256", "source_contract_id",
    "source_item_id", "target_item_id", "source_estimate_version_id",
    "source_section_index", "source_item_index", "source_item_key",
    "target_estimate_version_id", "target_section_index",
    "target_item_index", "target_item_key", "source_quantity_before",
    "source_quantity_after", "source_done_quantity", "confirmed_quantity",
    "transfer_quantity", "source_price_smeta", "source_price_brigade",
    "target_price_smeta", "target_price_brigade", "source_status",
    "contract_total_before", "contract_total_after", "applied_by_user_id",
    "applied_by_name", "applied_by_role", "applied_at",
}
SUPPLY_ALLOCATION_COLUMNS = {
    "id", "entry_id", "plan_id", "company_id", "project_id",
    "reconciliation_id", "plan_sha256", "request_id",
    "request_item_index", "request_item_snapshot", "request_item_sha256",
    "source_estimate_id", "source_estimate_version_id",
    "source_section_index", "source_item_index", "source_item_key",
    "source_sections_sha256", "target_estimate_id",
    "target_estimate_version_id", "target_section_index",
    "target_item_index", "target_item_key", "target_sections_sha256",
    "target_material_name", "target_unit", "target_work_package",
    "requested_quantity", "received_quantity",
    "previously_allocated_quantity", "allocation_quantity",
    "remaining_unallocated_quantity", "applied_by_user_id",
    "applied_by_name", "applied_by_role", "applied_at",
}
PLAN_CONSTRAINTS = {
    "pk_estimate_row_transfer_plans", "fk_etrp_reconciliation",
    "fk_etrp_base_estimate", "fk_etrp_target_estimate",
    "fk_etrp_target_version", "ck_etrp_owner", "ck_etrp_hashes",
    "ck_etrp_status", "ck_etrp_approval", "uq_etrp_id_owner",
    "uq_etrp_hash",
}
ENTRY_CONSTRAINTS = {
    "pk_estimate_row_transfer_entries", "fk_etre_plan_owner",
    "fk_etre_source_estimate", "fk_etre_source_version",
    "fk_etre_target_estimate", "fk_etre_target_version", "ck_etre_owner",
    "ck_etre_source_kind", "ck_etre_source_shape", "ck_etre_coordinates",
    "ck_etre_hashes", "ck_etre_quantities",
}
ASSIGNMENT_TRANSFER_CONSTRAINTS = {
    "pk_estimate_row_assignment_transfers", "fk_erat_entry_owner",
    "fk_erat_plan_owner", "fk_erat_reconciliation", "fk_erat_contract",
    "fk_erat_source_item", "fk_erat_target_item", "fk_erat_source_version",
    "fk_erat_target_version", "ck_erat_owner", "ck_erat_hash",
    "ck_erat_coordinates", "ck_erat_quantities", "ck_erat_prices",
    "ck_erat_totals", "ck_erat_actor", "uq_erat_entry",
}
SUPPLY_ALLOCATION_CONSTRAINTS = {
    "pk_estimate_row_supply_allocations", "fk_ersa_entry_owner",
    "fk_ersa_plan_owner", "fk_ersa_reconciliation", "fk_ersa_request",
    "fk_ersa_source_estimate", "fk_ersa_source_version",
    "fk_ersa_target_estimate", "fk_ersa_target_version", "ck_ersa_owner",
    "ck_ersa_hashes", "ck_ersa_coordinates", "ck_ersa_target_metadata",
    "ck_ersa_quantities", "ck_ersa_actor", "uq_ersa_entry",
}
INDEXES = {
    "idx_etrp_owner_created", "uq_etrp_single_approved", "idx_etre_plan",
    "uq_etre_assignment_source", "uq_etre_supply_source",
    "uq_etre_id_plan_owner", "idx_erat_plan", "idx_ersa_plan",
    "idx_ersa_request_item",
}
FUNCTIONS = {
    "reject_estimate_row_transfer_entry_mutation",
    "guard_estimate_row_transfer_plan_mutation",
    "guard_estimate_row_assignment_transfer",
    "guard_estimate_row_supply_allocation",
}
TRIGGERS = {
    "estimate_row_transfer_entry_immutable",
    "estimate_row_transfer_plan_guard",
    "estimate_row_assignment_transfer_guard",
    "estimate_row_supply_allocation_guard",
}

CONSTRAINT_SIGNATURES = {
    "pk_estimate_row_transfer_plans": ("PRIMARY KEY (id)",),
    "fk_etrp_reconciliation": (
        "FOREIGN KEY (reconciliation_id)",
        "REFERENCES estimate_reconciliations (id)",
        "ON DELETE RESTRICT",
    ),
    "fk_etrp_base_estimate": (
        "FOREIGN KEY (base_estimate_id)",
        "REFERENCES estimates (id)",
        "ON DELETE RESTRICT",
    ),
    "fk_etrp_target_estimate": (
        "FOREIGN KEY (target_estimate_id)",
        "REFERENCES estimates (id)",
        "ON DELETE RESTRICT",
    ),
    "fk_etrp_target_version": (
        "FOREIGN KEY (target_estimate_version_id)",
        "REFERENCES estimate_versions (id)",
        "ON DELETE RESTRICT",
    ),
    "ck_etrp_owner": (
        "company_id > 0", "project_id > 0",
        "base_snapshot_row_count >= 0", "target_snapshot_row_count >= 0",
    ),
    "ck_etrp_hashes": (
        "base_sections_sha256", "target_sections_sha256", "plan_sha256",
        "approved_plan_sha256", "[0-9a-f]{64}",
    ),
    "ck_etrp_status": ("status", "draft", "approved"),
    "ck_etrp_approval": (
        "approved_plan_sha256", "plan_sha256", "approved_by_user_id",
        "approved_by_name", "approved_by_role", "директор", "зам_директора",
        "approved_at",
    ),
    "uq_etrp_id_owner": ("UNIQUE (id, company_id, project_id)",),
    "uq_etrp_hash": ("UNIQUE (company_id, reconciliation_id, plan_sha256)",),
    "pk_estimate_row_transfer_entries": ("PRIMARY KEY (id)",),
    "fk_etre_plan_owner": (
        "FOREIGN KEY (plan_id, company_id, project_id)",
        "REFERENCES estimate_row_transfer_plans (id, company_id, project_id)",
        "ON DELETE RESTRICT",
    ),
    "fk_etre_source_estimate": (
        "FOREIGN KEY (source_estimate_id)",
        "REFERENCES estimates (id)",
        "ON DELETE RESTRICT",
    ),
    "fk_etre_source_version": (
        "FOREIGN KEY (source_estimate_version_id)",
        "REFERENCES estimate_versions (id)",
        "ON DELETE RESTRICT",
    ),
    "fk_etre_target_estimate": (
        "FOREIGN KEY (target_estimate_id)",
        "REFERENCES estimates (id)",
        "ON DELETE RESTRICT",
    ),
    "fk_etre_target_version": (
        "FOREIGN KEY (target_estimate_version_id)",
        "REFERENCES estimate_versions (id)",
        "ON DELETE RESTRICT",
    ),
    "ck_etre_owner": ("company_id > 0", "project_id > 0"),
    "ck_etre_source_kind": ("source_kind", "assignment", "supply"),
    "ck_etre_source_shape": (
        "source_kind", "assignment", "supply", "request_item_index",
        "source_parent_id = source_id",
    ),
    "ck_etre_coordinates": (
        "source_id > 0", "source_parent_id > 0", "source_estimate_id > 0",
        "source_estimate_version_id > 0", "source_section_index >= 0",
        "source_item_index >= 0", "source_item_key", "target_estimate_id > 0",
        "target_estimate_version_id > 0", "target_section_index >= 0",
        "target_item_index >= 0", "target_item_key",
    ),
    "ck_etre_hashes": (
        "source_sections_sha256", "target_sections_sha256", "[0-9a-f]{64}",
    ),
    "ck_etre_quantities": (
        "source_total_quantity >= 0", "source_protected_quantity >= 0",
        "source_available_quantity > 0", "quantity > 0",
        "source_protected_quantity <= source_total_quantity",
        "source_available_quantity = source_total_quantity - source_protected_quantity",
        "quantity <= source_available_quantity",
    ),
    "pk_estimate_row_assignment_transfers": ("PRIMARY KEY (id)",),
    "fk_erat_entry_owner": (
        "FOREIGN KEY (entry_id, plan_id, company_id, project_id)",
        "REFERENCES estimate_row_transfer_entries (id, plan_id, company_id, project_id)",
        "ON DELETE RESTRICT",
    ),
    "fk_erat_plan_owner": (
        "FOREIGN KEY (plan_id, company_id, project_id)",
        "REFERENCES estimate_row_transfer_plans (id, company_id, project_id)",
        "ON DELETE RESTRICT",
    ),
    "fk_erat_reconciliation": (
        "FOREIGN KEY (reconciliation_id)",
        "REFERENCES estimate_reconciliations (id)",
        "ON DELETE RESTRICT",
    ),
    "fk_erat_contract": (
        "FOREIGN KEY (source_contract_id)",
        "REFERENCES brigade_contracts (id)",
        "ON DELETE RESTRICT",
    ),
    "fk_erat_source_item": (
        "FOREIGN KEY (source_item_id)",
        "REFERENCES brigade_contract_items (id)",
        "ON DELETE RESTRICT",
    ),
    "fk_erat_target_item": (
        "FOREIGN KEY (target_item_id)",
        "REFERENCES brigade_contract_items (id)",
        "ON DELETE RESTRICT",
    ),
    "fk_erat_source_version": (
        "FOREIGN KEY (source_estimate_version_id)",
        "REFERENCES estimate_versions (id)",
        "ON DELETE RESTRICT",
    ),
    "fk_erat_target_version": (
        "FOREIGN KEY (target_estimate_version_id)",
        "REFERENCES estimate_versions (id)",
        "ON DELETE RESTRICT",
    ),
    "ck_erat_owner": (
        "company_id > 0", "project_id > 0", "reconciliation_id > 0",
        "source_contract_id > 0", "source_item_id > 0", "target_item_id > 0",
        "source_item_id <> target_item_id",
    ),
    "ck_erat_hash": ("plan_sha256", "[0-9a-f]{64}"),
    "ck_erat_coordinates": (
        "source_estimate_version_id > 0", "source_section_index >= 0",
        "source_item_index >= 0", "source_item_key",
        "target_estimate_version_id > 0", "target_section_index >= 0",
        "target_item_index >= 0", "target_item_key",
    ),
    "ck_erat_quantities": (
        "source_quantity_before > 0", "source_quantity_after >= 0",
        "source_done_quantity >= 0", "confirmed_quantity >= 0",
        "transfer_quantity > 0",
        "source_quantity_after = source_quantity_before - transfer_quantity",
        "source_done_quantity <= source_quantity_after",
        "confirmed_quantity <= source_quantity_after",
    ),
    "ck_erat_prices": (
        "source_price_smeta > 0", "source_price_brigade > 0",
        "target_price_smeta > 0", "target_price_brigade > 0",
        "source_price_brigade = target_price_brigade",
    ),
    "ck_erat_totals": (
        "contract_total_before >= 0", "contract_total_after >= 0",
        "contract_total_before = contract_total_after",
    ),
    "ck_erat_actor": (
        "applied_by_user_id > 0", "applied_by_name", "applied_by_role",
        "директор", "зам_директора", "source_status",
    ),
    "uq_erat_entry": ("UNIQUE (entry_id)",),
    "pk_estimate_row_supply_allocations": ("PRIMARY KEY (id)",),
    "fk_ersa_entry_owner": (
        "FOREIGN KEY (entry_id, plan_id, company_id, project_id)",
        "REFERENCES estimate_row_transfer_entries (id, plan_id, company_id, project_id)",
        "ON DELETE RESTRICT",
    ),
    "fk_ersa_plan_owner": (
        "FOREIGN KEY (plan_id, company_id, project_id)",
        "REFERENCES estimate_row_transfer_plans (id, company_id, project_id)",
        "ON DELETE RESTRICT",
    ),
    "fk_ersa_reconciliation": (
        "FOREIGN KEY (reconciliation_id)",
        "REFERENCES estimate_reconciliations (id)", "ON DELETE RESTRICT",
    ),
    "fk_ersa_request": (
        "FOREIGN KEY (request_id)", "REFERENCES supply_requests (id)",
        "ON DELETE RESTRICT",
    ),
    "fk_ersa_source_estimate": (
        "FOREIGN KEY (source_estimate_id)", "REFERENCES estimates (id)",
        "ON DELETE RESTRICT",
    ),
    "fk_ersa_source_version": (
        "FOREIGN KEY (source_estimate_version_id)",
        "REFERENCES estimate_versions (id)", "ON DELETE RESTRICT",
    ),
    "fk_ersa_target_estimate": (
        "FOREIGN KEY (target_estimate_id)", "REFERENCES estimates (id)",
        "ON DELETE RESTRICT",
    ),
    "fk_ersa_target_version": (
        "FOREIGN KEY (target_estimate_version_id)",
        "REFERENCES estimate_versions (id)", "ON DELETE RESTRICT",
    ),
    "ck_ersa_owner": (
        "company_id > 0", "project_id > 0", "reconciliation_id > 0",
        "request_id > 0", "request_item_index >= 0",
    ),
    "ck_ersa_hashes": (
        "plan_sha256", "request_item_sha256", "source_sections_sha256",
        "target_sections_sha256", "[0-9a-f]{64}",
    ),
    "ck_ersa_coordinates": (
        "source_estimate_id > 0", "source_estimate_version_id > 0",
        "source_section_index >= 0", "source_item_index >= 0",
        "source_item_key", "target_estimate_id > 0",
        "target_estimate_version_id > 0", "target_section_index >= 0",
        "target_item_index >= 0", "target_item_key",
    ),
    "ck_ersa_target_metadata": (
        "target_material_name", "target_unit", "target_work_package",
    ),
    "ck_ersa_quantities": (
        "requested_quantity > 0", "received_quantity >= 0",
        "previously_allocated_quantity >= 0", "allocation_quantity > 0",
        "remaining_unallocated_quantity >= 0",
        "requested_quantity = received_quantity + previously_allocated_quantity + allocation_quantity + remaining_unallocated_quantity",
    ),
    "ck_ersa_actor": (
        "applied_by_user_id > 0", "applied_by_name", "applied_by_role",
        "директор", "зам_директора",
    ),
    "uq_ersa_entry": ("UNIQUE (entry_id)",),
}
INDEX_SIGNATURES = {
    "idx_etrp_owner_created": (
        "ON estimate_row_transfer_plans",
        "company_id, project_id, created_at DESC, id DESC",
    ),
    "uq_etrp_single_approved": (
        "CREATE UNIQUE INDEX", "ON estimate_row_transfer_plans",
        "company_id, reconciliation_id", "WHERE", "status", "approved",
    ),
    "idx_etre_plan": ("ON estimate_row_transfer_entries", "plan_id, id"),
    "uq_etre_assignment_source": (
        "CREATE UNIQUE INDEX", "ON estimate_row_transfer_entries",
        "plan_id, source_id", "WHERE", "source_kind", "assignment",
    ),
    "uq_etre_supply_source": (
        "CREATE UNIQUE INDEX", "ON estimate_row_transfer_entries",
        "plan_id, source_id, request_item_index", "WHERE", "source_kind", "supply",
    ),
    "uq_etre_id_plan_owner": (
        "CREATE UNIQUE INDEX", "ON estimate_row_transfer_entries",
        "id, plan_id, company_id, project_id",
    ),
    "idx_erat_plan": (
        "ON estimate_row_assignment_transfers", "plan_id, id",
    ),
    "idx_ersa_plan": (
        "ON estimate_row_supply_allocations", "plan_id, id",
    ),
    "idx_ersa_request_item": (
        "ON estimate_row_supply_allocations",
        "company_id, request_id, request_item_index, id",
    ),
}
FUNCTION_SIGNATURES = {
    "reject_estimate_row_transfer_entry_mutation": (
        "reject_estimate_row_transfer_entry_mutation", "RETURNS trigger",
        "estimate_row_transfer_entry_immutable",
    ),
    "guard_estimate_row_transfer_plan_mutation": (
        "guard_estimate_row_transfer_plan_mutation", "RETURNS trigger",
        "estimate_row_transfer_plan_immutable",
        "estimate_row_transfer_plan_transition_invalid",
        "estimate_row_transfer_plan_mutation_invalid",
        "OLD.status", "NEW.status", "NEW.plan_sha256", "OLD.plan_sha256",
        "approved_by_user_id", "approved_by_role", "директор", "зам_директора",
    ),
    "guard_estimate_row_assignment_transfer": (
        "guard_estimate_row_assignment_transfer", "RETURNS trigger",
        "estimate_row_assignment_transfer_immutable",
        "estimate_row_assignment_transfer_invalid", "source_kind", "assignment",
        "approved_plan_sha256", "brigade_contract_items", "work_journal",
        "source_total_quantity", "source_protected_quantity",
        "source_quantity_before", "source_quantity_after", "source_status",
        "target_price_brigade", "work_package",
    ),
    "guard_estimate_row_supply_allocation": (
        "guard_estimate_row_supply_allocation", "RETURNS trigger",
        "estimate_row_supply_allocation_immutable",
        "estimate_row_supply_allocation_invalid", "source_kind", "supply",
        "approved_plan_sha256", "supply_requests", "supply_deliveries",
        "previously_allocated_quantity", "remaining_unallocated_quantity",
        "request_item_snapshot", "target_material_name",
    ),
}
TRIGGER_SIGNATURES = {
    "estimate_row_transfer_entry_immutable": (
        "BEFORE", "UPDATE", "DELETE", "ON estimate_row_transfer_entries",
        "EXECUTE FUNCTION reject_estimate_row_transfer_entry_mutation",
    ),
    "estimate_row_transfer_plan_guard": (
        "BEFORE", "UPDATE", "DELETE", "ON estimate_row_transfer_plans",
        "EXECUTE FUNCTION guard_estimate_row_transfer_plan_mutation",
    ),
    "estimate_row_assignment_transfer_guard": (
        "BEFORE", "INSERT", "UPDATE", "DELETE",
        "ON estimate_row_assignment_transfers",
        "EXECUTE FUNCTION guard_estimate_row_assignment_transfer",
    ),
    "estimate_row_supply_allocation_guard": (
        "BEFORE", "INSERT", "UPDATE", "DELETE",
        "ON estimate_row_supply_allocations",
        "EXECUTE FUNCTION guard_estimate_row_supply_allocation",
    ),
}


class SchemaMigrationError(RuntimeError):
    pass


CREATE_PLANS_TABLE = """
CREATE TABLE public.estimate_row_transfer_plans (
    id BIGSERIAL,
    company_id INTEGER NOT NULL,
    project_id INTEGER NOT NULL,
    work_package VARCHAR(100) NOT NULL,
    smeta_type VARCHAR(50) NOT NULL,
    reconciliation_id INTEGER NOT NULL,
    base_estimate_id INTEGER NOT NULL,
    target_estimate_id INTEGER NOT NULL,
    target_estimate_version_id INTEGER NOT NULL,
    base_sections_sha256 CHAR(64) NOT NULL,
    target_sections_sha256 CHAR(64) NOT NULL,
    base_snapshot_row_count INTEGER NOT NULL,
    target_snapshot_row_count INTEGER NOT NULL,
    plan_sha256 CHAR(64) NOT NULL,
    approved_plan_sha256 CHAR(64),
    status VARCHAR(20) NOT NULL DEFAULT 'draft',
    created_by_user_id INTEGER NOT NULL,
    created_by_name TEXT NOT NULL,
    created_by_role VARCHAR(100) NOT NULL,
    approved_by_user_id INTEGER,
    approved_by_name TEXT,
    approved_by_role VARCHAR(100),
    approved_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT pk_estimate_row_transfer_plans PRIMARY KEY (id),
    CONSTRAINT fk_etrp_reconciliation FOREIGN KEY (reconciliation_id)
        REFERENCES public.estimate_reconciliations(id) ON DELETE RESTRICT,
    CONSTRAINT fk_etrp_base_estimate FOREIGN KEY (base_estimate_id)
        REFERENCES public.estimates(id) ON DELETE RESTRICT,
    CONSTRAINT fk_etrp_target_estimate FOREIGN KEY (target_estimate_id)
        REFERENCES public.estimates(id) ON DELETE RESTRICT,
    CONSTRAINT fk_etrp_target_version FOREIGN KEY (target_estimate_version_id)
        REFERENCES public.estimate_versions(id) ON DELETE RESTRICT,
    CONSTRAINT ck_etrp_owner CHECK (
        company_id>0 AND project_id>0
        AND base_snapshot_row_count>=0 AND target_snapshot_row_count>=0
    ),
    CONSTRAINT ck_etrp_hashes CHECK (
        base_sections_sha256 ~ '^[0-9a-f]{64}$'
        AND target_sections_sha256 ~ '^[0-9a-f]{64}$'
        AND plan_sha256 ~ '^[0-9a-f]{64}$'
        AND (approved_plan_sha256 IS NULL
             OR approved_plan_sha256 ~ '^[0-9a-f]{64}$')
    ),
    CONSTRAINT ck_etrp_status CHECK (status IN ('draft','approved')),
    CONSTRAINT ck_etrp_approval CHECK (
        (status='draft' AND approved_plan_sha256 IS NULL
         AND approved_by_user_id IS NULL AND approved_by_name IS NULL
         AND approved_by_role IS NULL AND approved_at IS NULL)
        OR
        (status='approved' AND approved_plan_sha256=plan_sha256
         AND approved_by_user_id>0 AND approved_by_name IS NOT NULL
         AND approved_by_role IN ('директор','зам_директора')
         AND approved_at IS NOT NULL)
    ),
    CONSTRAINT uq_etrp_id_owner UNIQUE (id,company_id,project_id),
    CONSTRAINT uq_etrp_hash UNIQUE (company_id,reconciliation_id,plan_sha256)
)
"""

CREATE_ENTRIES_TABLE = """
CREATE TABLE public.estimate_row_transfer_entries (
    id BIGSERIAL,
    plan_id BIGINT NOT NULL,
    company_id INTEGER NOT NULL,
    project_id INTEGER NOT NULL,
    source_kind VARCHAR(20) NOT NULL,
    source_id INTEGER NOT NULL,
    source_parent_id INTEGER NOT NULL,
    request_item_index INTEGER,
    source_estimate_id INTEGER NOT NULL,
    source_estimate_version_id INTEGER NOT NULL,
    source_section_index INTEGER NOT NULL,
    source_item_index INTEGER NOT NULL,
    source_item_key VARCHAR(255) NOT NULL,
    source_sections_sha256 CHAR(64) NOT NULL,
    target_estimate_id INTEGER NOT NULL,
    target_estimate_version_id INTEGER NOT NULL,
    target_section_index INTEGER NOT NULL,
    target_item_index INTEGER NOT NULL,
    target_item_key VARCHAR(255) NOT NULL,
    target_sections_sha256 CHAR(64) NOT NULL,
    source_total_quantity NUMERIC(20,6) NOT NULL,
    source_protected_quantity NUMERIC(20,6) NOT NULL,
    source_available_quantity NUMERIC(20,6) NOT NULL,
    quantity NUMERIC(20,6) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT pk_estimate_row_transfer_entries PRIMARY KEY (id),
    CONSTRAINT fk_etre_plan_owner FOREIGN KEY (plan_id,company_id,project_id)
        REFERENCES public.estimate_row_transfer_plans(id,company_id,project_id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_etre_source_estimate FOREIGN KEY (source_estimate_id)
        REFERENCES public.estimates(id) ON DELETE RESTRICT,
    CONSTRAINT fk_etre_source_version FOREIGN KEY (source_estimate_version_id)
        REFERENCES public.estimate_versions(id) ON DELETE RESTRICT,
    CONSTRAINT fk_etre_target_estimate FOREIGN KEY (target_estimate_id)
        REFERENCES public.estimates(id) ON DELETE RESTRICT,
    CONSTRAINT fk_etre_target_version FOREIGN KEY (target_estimate_version_id)
        REFERENCES public.estimate_versions(id) ON DELETE RESTRICT,
    CONSTRAINT ck_etre_owner CHECK (company_id>0 AND project_id>0),
    CONSTRAINT ck_etre_source_kind CHECK (source_kind IN ('assignment','supply')),
    CONSTRAINT ck_etre_source_shape CHECK (
        (source_kind='assignment' AND request_item_index IS NULL)
        OR
        (source_kind='supply' AND request_item_index>=0
         AND source_parent_id=source_id)
    ),
    CONSTRAINT ck_etre_coordinates CHECK (
        source_id>0 AND source_parent_id>0 AND source_estimate_id>0
        AND source_estimate_version_id>0 AND source_section_index>=0
        AND source_item_index>=0 AND source_item_key<>''
        AND target_estimate_id>0 AND target_estimate_version_id>0
        AND target_section_index>=0 AND target_item_index>=0
        AND target_item_key<>''
    ),
    CONSTRAINT ck_etre_hashes CHECK (
        source_sections_sha256 ~ '^[0-9a-f]{64}$'
        AND target_sections_sha256 ~ '^[0-9a-f]{64}$'
    ),
    CONSTRAINT ck_etre_quantities CHECK (
        source_total_quantity>=0 AND source_protected_quantity>=0
        AND source_available_quantity>0 AND quantity>0
        AND source_protected_quantity<=source_total_quantity
        AND source_available_quantity=source_total_quantity-source_protected_quantity
        AND quantity<=source_available_quantity
    )
)
"""

CREATE_ASSIGNMENT_TRANSFERS_TABLE = """
CREATE TABLE public.estimate_row_assignment_transfers (
    id BIGSERIAL,
    entry_id BIGINT NOT NULL,
    plan_id BIGINT NOT NULL,
    company_id INTEGER NOT NULL,
    project_id INTEGER NOT NULL,
    reconciliation_id INTEGER NOT NULL,
    plan_sha256 CHAR(64) NOT NULL,
    source_contract_id INTEGER NOT NULL,
    source_item_id INTEGER NOT NULL,
    target_item_id INTEGER NOT NULL,
    source_estimate_version_id INTEGER NOT NULL,
    source_section_index INTEGER NOT NULL,
    source_item_index INTEGER NOT NULL,
    source_item_key VARCHAR(255) NOT NULL,
    target_estimate_version_id INTEGER NOT NULL,
    target_section_index INTEGER NOT NULL,
    target_item_index INTEGER NOT NULL,
    target_item_key VARCHAR(255) NOT NULL,
    source_quantity_before NUMERIC(20,6) NOT NULL,
    source_quantity_after NUMERIC(20,6) NOT NULL,
    source_done_quantity NUMERIC(20,6) NOT NULL,
    confirmed_quantity NUMERIC(20,6) NOT NULL,
    transfer_quantity NUMERIC(20,6) NOT NULL,
    source_price_smeta NUMERIC(20,6) NOT NULL,
    source_price_brigade NUMERIC(20,6) NOT NULL,
    target_price_smeta NUMERIC(20,6) NOT NULL,
    target_price_brigade NUMERIC(20,6) NOT NULL,
    source_status VARCHAR(50) NOT NULL,
    contract_total_before NUMERIC(20,2) NOT NULL,
    contract_total_after NUMERIC(20,2) NOT NULL,
    applied_by_user_id INTEGER NOT NULL,
    applied_by_name TEXT NOT NULL,
    applied_by_role VARCHAR(100) NOT NULL,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT pk_estimate_row_assignment_transfers PRIMARY KEY (id),
    CONSTRAINT fk_erat_entry_owner
        FOREIGN KEY (entry_id,plan_id,company_id,project_id)
        REFERENCES public.estimate_row_transfer_entries(id,plan_id,company_id,project_id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_erat_plan_owner FOREIGN KEY (plan_id,company_id,project_id)
        REFERENCES public.estimate_row_transfer_plans(id,company_id,project_id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_erat_reconciliation FOREIGN KEY (reconciliation_id)
        REFERENCES public.estimate_reconciliations(id) ON DELETE RESTRICT,
    CONSTRAINT fk_erat_contract FOREIGN KEY (source_contract_id)
        REFERENCES public.brigade_contracts(id) ON DELETE RESTRICT,
    CONSTRAINT fk_erat_source_item FOREIGN KEY (source_item_id)
        REFERENCES public.brigade_contract_items(id) ON DELETE RESTRICT,
    CONSTRAINT fk_erat_target_item FOREIGN KEY (target_item_id)
        REFERENCES public.brigade_contract_items(id) ON DELETE RESTRICT,
    CONSTRAINT fk_erat_source_version FOREIGN KEY (source_estimate_version_id)
        REFERENCES public.estimate_versions(id) ON DELETE RESTRICT,
    CONSTRAINT fk_erat_target_version FOREIGN KEY (target_estimate_version_id)
        REFERENCES public.estimate_versions(id) ON DELETE RESTRICT,
    CONSTRAINT ck_erat_owner CHECK (
        company_id>0 AND project_id>0 AND reconciliation_id>0
        AND source_contract_id>0 AND source_item_id>0 AND target_item_id>0
        AND source_item_id<>target_item_id
    ),
    CONSTRAINT ck_erat_hash CHECK (plan_sha256 ~ '^[0-9a-f]{64}$'),
    CONSTRAINT ck_erat_coordinates CHECK (
        source_estimate_version_id>0 AND source_section_index>=0
        AND source_item_index>=0 AND source_item_key<>''
        AND target_estimate_version_id>0 AND target_section_index>=0
        AND target_item_index>=0 AND target_item_key<>''
    ),
    CONSTRAINT ck_erat_quantities CHECK (
        source_quantity_before>0 AND source_quantity_after>=0
        AND source_done_quantity>=0 AND confirmed_quantity>=0
        AND transfer_quantity>0
        AND source_quantity_after=source_quantity_before-transfer_quantity
        AND source_done_quantity<=source_quantity_after
        AND confirmed_quantity<=source_quantity_after
        AND source_quantity_before NOT IN
            ('NaN'::numeric,'Infinity'::numeric,'-Infinity'::numeric)
        AND source_quantity_after NOT IN
            ('NaN'::numeric,'Infinity'::numeric,'-Infinity'::numeric)
        AND source_done_quantity NOT IN
            ('NaN'::numeric,'Infinity'::numeric,'-Infinity'::numeric)
        AND confirmed_quantity NOT IN
            ('NaN'::numeric,'Infinity'::numeric,'-Infinity'::numeric)
        AND transfer_quantity NOT IN
            ('NaN'::numeric,'Infinity'::numeric,'-Infinity'::numeric)
    ),
    CONSTRAINT ck_erat_prices CHECK (
        source_price_smeta>0 AND source_price_brigade>0
        AND target_price_smeta>0 AND target_price_brigade>0
        AND source_price_brigade=target_price_brigade
        AND source_price_smeta NOT IN
            ('NaN'::numeric,'Infinity'::numeric,'-Infinity'::numeric)
        AND source_price_brigade NOT IN
            ('NaN'::numeric,'Infinity'::numeric,'-Infinity'::numeric)
        AND target_price_smeta NOT IN
            ('NaN'::numeric,'Infinity'::numeric,'-Infinity'::numeric)
        AND target_price_brigade NOT IN
            ('NaN'::numeric,'Infinity'::numeric,'-Infinity'::numeric)
    ),
    CONSTRAINT ck_erat_totals CHECK (
        contract_total_before>=0 AND contract_total_after>=0
        AND contract_total_before=contract_total_after
        AND contract_total_before NOT IN
            ('NaN'::numeric,'Infinity'::numeric,'-Infinity'::numeric)
        AND contract_total_after NOT IN
            ('NaN'::numeric,'Infinity'::numeric,'-Infinity'::numeric)
    ),
    CONSTRAINT ck_erat_actor CHECK (
        applied_by_user_id>0 AND btrim(applied_by_name)<>''
        AND applied_by_role IN ('директор','зам_директора')
        AND btrim(source_status)<>''
    ),
    CONSTRAINT uq_erat_entry UNIQUE (entry_id)
)
"""

CREATE_SUPPLY_ALLOCATIONS_TABLE = """
CREATE TABLE public.estimate_row_supply_allocations (
    id BIGSERIAL,
    entry_id BIGINT NOT NULL,
    plan_id BIGINT NOT NULL,
    company_id INTEGER NOT NULL,
    project_id INTEGER NOT NULL,
    reconciliation_id INTEGER NOT NULL,
    plan_sha256 CHAR(64) NOT NULL,
    request_id INTEGER NOT NULL,
    request_item_index INTEGER NOT NULL,
    request_item_snapshot JSONB NOT NULL,
    request_item_sha256 CHAR(64) NOT NULL,
    source_estimate_id INTEGER NOT NULL,
    source_estimate_version_id INTEGER NOT NULL,
    source_section_index INTEGER NOT NULL,
    source_item_index INTEGER NOT NULL,
    source_item_key VARCHAR(255) NOT NULL,
    source_sections_sha256 CHAR(64) NOT NULL,
    target_estimate_id INTEGER NOT NULL,
    target_estimate_version_id INTEGER NOT NULL,
    target_section_index INTEGER NOT NULL,
    target_item_index INTEGER NOT NULL,
    target_item_key VARCHAR(255) NOT NULL,
    target_sections_sha256 CHAR(64) NOT NULL,
    target_material_name TEXT NOT NULL,
    target_unit VARCHAR(50) NOT NULL,
    target_work_package VARCHAR(100) NOT NULL,
    requested_quantity NUMERIC(20,6) NOT NULL,
    received_quantity NUMERIC(20,6) NOT NULL,
    previously_allocated_quantity NUMERIC(20,6) NOT NULL,
    allocation_quantity NUMERIC(20,6) NOT NULL,
    remaining_unallocated_quantity NUMERIC(20,6) NOT NULL,
    applied_by_user_id INTEGER NOT NULL,
    applied_by_name TEXT NOT NULL,
    applied_by_role VARCHAR(100) NOT NULL,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT pk_estimate_row_supply_allocations PRIMARY KEY (id),
    CONSTRAINT fk_ersa_entry_owner
        FOREIGN KEY (entry_id,plan_id,company_id,project_id)
        REFERENCES public.estimate_row_transfer_entries(id,plan_id,company_id,project_id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_ersa_plan_owner FOREIGN KEY (plan_id,company_id,project_id)
        REFERENCES public.estimate_row_transfer_plans(id,company_id,project_id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_ersa_reconciliation FOREIGN KEY (reconciliation_id)
        REFERENCES public.estimate_reconciliations(id) ON DELETE RESTRICT,
    CONSTRAINT fk_ersa_request FOREIGN KEY (request_id)
        REFERENCES public.supply_requests(id) ON DELETE RESTRICT,
    CONSTRAINT fk_ersa_source_estimate FOREIGN KEY (source_estimate_id)
        REFERENCES public.estimates(id) ON DELETE RESTRICT,
    CONSTRAINT fk_ersa_source_version FOREIGN KEY (source_estimate_version_id)
        REFERENCES public.estimate_versions(id) ON DELETE RESTRICT,
    CONSTRAINT fk_ersa_target_estimate FOREIGN KEY (target_estimate_id)
        REFERENCES public.estimates(id) ON DELETE RESTRICT,
    CONSTRAINT fk_ersa_target_version FOREIGN KEY (target_estimate_version_id)
        REFERENCES public.estimate_versions(id) ON DELETE RESTRICT,
    CONSTRAINT ck_ersa_owner CHECK (
        company_id>0 AND project_id>0 AND reconciliation_id>0
        AND request_id>0 AND request_item_index>=0
    ),
    CONSTRAINT ck_ersa_hashes CHECK (
        plan_sha256 ~ '^[0-9a-f]{64}$'
        AND request_item_sha256 ~ '^[0-9a-f]{64}$'
        AND source_sections_sha256 ~ '^[0-9a-f]{64}$'
        AND target_sections_sha256 ~ '^[0-9a-f]{64}$'
    ),
    CONSTRAINT ck_ersa_coordinates CHECK (
        source_estimate_id>0 AND source_estimate_version_id>0
        AND source_section_index>=0 AND source_item_index>=0
        AND source_item_key<>'' AND target_estimate_id>0
        AND target_estimate_version_id>0 AND target_section_index>=0
        AND target_item_index>=0 AND target_item_key<>''
    ),
    CONSTRAINT ck_ersa_target_metadata CHECK (
        btrim(target_material_name)<>'' AND btrim(target_unit)<>''
        AND btrim(target_work_package)<>''
    ),
    CONSTRAINT ck_ersa_quantities CHECK (
        requested_quantity>0 AND received_quantity>=0
        AND previously_allocated_quantity>=0 AND allocation_quantity>0
        AND remaining_unallocated_quantity>=0
        AND requested_quantity=
            received_quantity+previously_allocated_quantity
            +allocation_quantity+remaining_unallocated_quantity
        AND requested_quantity NOT IN
            ('NaN'::numeric,'Infinity'::numeric,'-Infinity'::numeric)
        AND received_quantity NOT IN
            ('NaN'::numeric,'Infinity'::numeric,'-Infinity'::numeric)
        AND previously_allocated_quantity NOT IN
            ('NaN'::numeric,'Infinity'::numeric,'-Infinity'::numeric)
        AND allocation_quantity NOT IN
            ('NaN'::numeric,'Infinity'::numeric,'-Infinity'::numeric)
        AND remaining_unallocated_quantity NOT IN
            ('NaN'::numeric,'Infinity'::numeric,'-Infinity'::numeric)
    ),
    CONSTRAINT ck_ersa_actor CHECK (
        applied_by_user_id>0 AND btrim(applied_by_name)<>''
        AND applied_by_role IN ('директор','зам_директора')
    ),
    CONSTRAINT uq_ersa_entry UNIQUE (entry_id)
)
"""

ENTRY_GUARD_FUNCTION = """
CREATE FUNCTION public.reject_estimate_row_transfer_entry_mutation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'estimate_row_transfer_entry_immutable';
END
$$
"""

PLAN_GUARD_FUNCTION = """
CREATE FUNCTION public.guard_estimate_row_transfer_plan_mutation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP='DELETE' THEN
        RAISE EXCEPTION 'estimate_row_transfer_plan_immutable';
    END IF;
    IF OLD.status<>'draft' OR NEW.status<>'approved' THEN
        RAISE EXCEPTION 'estimate_row_transfer_plan_transition_invalid';
    END IF;
    IF ROW(
        NEW.id,NEW.company_id,NEW.project_id,NEW.work_package,NEW.smeta_type,
        NEW.reconciliation_id,NEW.base_estimate_id,NEW.target_estimate_id,
        NEW.target_estimate_version_id,NEW.base_sections_sha256,
        NEW.target_sections_sha256,NEW.base_snapshot_row_count,
        NEW.target_snapshot_row_count,NEW.plan_sha256,NEW.created_by_user_id,
        NEW.created_by_name,NEW.created_by_role,NEW.created_at
    ) IS DISTINCT FROM ROW(
        OLD.id,OLD.company_id,OLD.project_id,OLD.work_package,OLD.smeta_type,
        OLD.reconciliation_id,OLD.base_estimate_id,OLD.target_estimate_id,
        OLD.target_estimate_version_id,OLD.base_sections_sha256,
        OLD.target_sections_sha256,OLD.base_snapshot_row_count,
        OLD.target_snapshot_row_count,OLD.plan_sha256,OLD.created_by_user_id,
        OLD.created_by_name,OLD.created_by_role,OLD.created_at
    ) OR NEW.approved_plan_sha256 IS DISTINCT FROM OLD.plan_sha256
      OR NEW.approved_by_user_id IS NULL OR NEW.approved_by_name IS NULL
      OR NEW.approved_by_role NOT IN ('директор','зам_директора')
      OR NEW.approved_at IS NULL OR NEW.updated_at<OLD.updated_at THEN
        RAISE EXCEPTION 'estimate_row_transfer_plan_mutation_invalid';
    END IF;
    RETURN NEW;
END
$$
"""

ASSIGNMENT_TRANSFER_GUARD_FUNCTION = """
CREATE FUNCTION public.guard_estimate_row_assignment_transfer()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP<>'INSERT' THEN
        RAISE EXCEPTION 'estimate_row_assignment_transfer_immutable'
          USING ERRCODE='23514';
    END IF;
    IF NOT EXISTS (
        SELECT 1
          FROM public.estimate_row_transfer_entries e
          JOIN public.estimate_row_transfer_plans p
            ON p.id=e.plan_id AND p.company_id=e.company_id
           AND p.project_id=e.project_id
          JOIN public.brigade_contracts bc
            ON bc.id=NEW.source_contract_id
          JOIN public.brigade_contract_items source_item
            ON source_item.id=NEW.source_item_id
          JOIN public.brigade_contract_items target_item
            ON target_item.id=NEW.target_item_id
         WHERE e.id=NEW.entry_id AND e.plan_id=NEW.plan_id
           AND e.company_id=NEW.company_id AND e.project_id=NEW.project_id
           AND e.source_kind='assignment'
           AND e.source_id=NEW.source_item_id
           AND e.source_parent_id=NEW.source_contract_id
           AND e.source_estimate_version_id=NEW.source_estimate_version_id
           AND e.source_section_index=NEW.source_section_index
           AND e.source_item_index=NEW.source_item_index
           AND e.source_item_key=NEW.source_item_key
           AND e.target_estimate_version_id=NEW.target_estimate_version_id
           AND e.target_section_index=NEW.target_section_index
           AND e.target_item_index=NEW.target_item_index
           AND e.target_item_key=NEW.target_item_key
           AND e.source_total_quantity=NEW.source_quantity_before
           AND e.source_protected_quantity=NEW.confirmed_quantity
           AND e.source_available_quantity=
               NEW.source_quantity_before-NEW.confirmed_quantity
           AND e.quantity=NEW.transfer_quantity
           AND p.reconciliation_id=NEW.reconciliation_id
           AND p.status='approved' AND p.plan_sha256=NEW.plan_sha256
           AND p.approved_plan_sha256=NEW.plan_sha256
           AND bc.company_id=NEW.company_id AND bc.project_id=NEW.project_id
           AND COALESCE(NULLIF(bc.work_package,''),'Основная')=p.work_package
           AND bc.total_amount=NEW.contract_total_after
           AND source_item.contract_id=NEW.source_contract_id
           AND COALESCE(NULLIF(source_item.work_package,''),'Основная')=p.work_package
           AND source_item.source_type='estimate'
           AND source_item.source_estimate_version_id=NEW.source_estimate_version_id
           AND source_item.source_section_index=NEW.source_section_index
           AND source_item.source_item_index=NEW.source_item_index
           AND source_item.source_item_key=NEW.source_item_key
           AND source_item.estimate_item_key=NEW.source_item_key
           AND source_item.quantity::numeric=NEW.source_quantity_after
           AND source_item.done_quantity::numeric=NEW.source_done_quantity
           AND source_item.price_smeta=NEW.source_price_smeta
           AND source_item.price_brigade=NEW.source_price_brigade
           AND source_item.status=NEW.source_status
           AND target_item.contract_id=NEW.source_contract_id
           AND COALESCE(NULLIF(target_item.work_package,''),'Основная')=p.work_package
           AND target_item.source_type='estimate'
           AND target_item.source_estimate_version_id=NEW.target_estimate_version_id
           AND target_item.source_section_index=NEW.target_section_index
           AND target_item.source_item_index=NEW.target_item_index
           AND target_item.source_item_key=NEW.target_item_key
           AND target_item.estimate_item_key=NEW.target_item_key
           AND target_item.quantity::numeric=NEW.transfer_quantity
           AND target_item.done_quantity::numeric=0
           AND target_item.price_smeta=NEW.target_price_smeta
           AND target_item.price_brigade=NEW.target_price_brigade
           AND COALESCE((
               SELECT SUM(wj.quantity::numeric)
                 FROM public.work_journal wj
                WHERE wj.contract_item_id=NEW.source_item_id
                  AND wj.status='Подтверждено'
           ),0)=NEW.confirmed_quantity
    ) THEN
        RAISE EXCEPTION 'estimate_row_assignment_transfer_invalid'
          USING ERRCODE='23514';
    END IF;
    RETURN NEW;
END
$$
"""

SUPPLY_ALLOCATION_GUARD_FUNCTION = """
CREATE FUNCTION public.guard_estimate_row_supply_allocation()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    live_items JSONB;
    live_item JSONB;
    live_project_name TEXT;
    live_received NUMERIC;
    live_prior NUMERIC;
BEGIN
    IF TG_OP<>'INSERT' THEN
        RAISE EXCEPTION 'estimate_row_supply_allocation_immutable'
          USING ERRCODE='23514';
    END IF;

    SELECT sr.items_json::jsonb,
           sr.items_json::jsonb -> NEW.request_item_index,
           sr.project
      INTO live_items,live_item,live_project_name
      FROM public.supply_requests sr
      JOIN public.projects project_owner
        ON project_owner.id=NEW.project_id
       AND project_owner.company_id=NEW.company_id
       AND project_owner.name=sr.project
     WHERE sr.id=NEW.request_id
       AND sr.company_id=NEW.company_id
       AND COALESCE(NULLIF(sr.work_package,''),'Основная')=
           NEW.target_work_package
       AND COALESCE(sr.status,'') IN (
           'Новая','Подтверждена прорабом','Утверждена','КП запрошены'
       );

    SELECT COALESCE(SUM(allocation.allocation_quantity),0)
      INTO live_prior
      FROM public.estimate_row_supply_allocations allocation
     WHERE allocation.company_id=NEW.company_id
       AND allocation.request_id=NEW.request_id
       AND allocation.request_item_index=NEW.request_item_index;

    SELECT COALESCE(SUM(delivery.received_quantity::numeric),0)
      INTO live_received
      FROM public.supply_deliveries delivery
     WHERE delivery.request_id=NEW.request_id
       AND delivery.company_id=NEW.company_id
       AND delivery.material_name=
           COALESCE(live_item->>'materialName',live_item->>'name','')
       AND delivery.unit=COALESCE(live_item->>'unit','');

    IF live_item IS NULL
       OR live_item IS DISTINCT FROM NEW.request_item_snapshot
       OR live_prior IS DISTINCT FROM NEW.previously_allocated_quantity
       OR live_received IS DISTINCT FROM NEW.received_quantity
       OR NEW.remaining_unallocated_quantity IS DISTINCT FROM
          NEW.requested_quantity-NEW.received_quantity
          -NEW.previously_allocated_quantity-NEW.allocation_quantity
       OR EXISTS (
           SELECT 1 FROM public.supply_deliveries delivery
            WHERE delivery.request_id=NEW.request_id
              AND delivery.company_id IS DISTINCT FROM NEW.company_id
       )
       OR jsonb_typeof(live_item)<>'object'
       OR live_item->>'sourceType'<>'estimate_material_control'
       OR live_item #>> '{estimateLineage,version}' NOT IN ('1','2')
       OR (
           live_item #>> '{estimateLineage,version}'='2'
           AND (
               COALESCE(live_item #>> '{estimateLineage,companyId}','')
                   !~ '^[1-9][0-9]*$'
               OR COALESCE(live_item #>> '{estimateLineage,projectId}','')
                   !~ '^[1-9][0-9]*$'
               OR (live_item #>> '{estimateLineage,companyId}')::integer
                   <>NEW.company_id
               OR (live_item #>> '{estimateLineage,projectId}')::integer
                   <>NEW.project_id
           )
       )
       OR live_item #>> '{estimateLineage,validated}'<>'true'
       OR live_item #>> '{estimateLineage,projectName}'<>live_project_name
       OR COALESCE(NULLIF(live_item->>'workPackage',''),'Основная')
            <>NEW.target_work_package
       OR COALESCE(NULLIF(live_item #>> '{estimateLineage,workPackage}',''),'Основная')
            <>NEW.target_work_package
       OR jsonb_typeof(live_item #> '{estimateLineage,sources}')<>'array'
       OR jsonb_array_length(live_item #> '{estimateLineage,sources}')<>1
       OR live_item #>> '{estimateLineage,sources,0,validated}'<>'true'
       OR (live_item #>> '{estimateLineage,sources,0,estimateId}')::integer
            <>NEW.source_estimate_id
       OR (live_item #>> '{estimateLineage,sources,0,sectionIndex}')::integer
            <>NEW.source_section_index
       OR (live_item #>> '{estimateLineage,sources,0,itemIndex}')::integer
            <>NEW.source_item_index
       OR live_item #>> '{estimateLineage,sources,0,materialName}'
            <>COALESCE(live_item->>'materialName',live_item->>'name','')
       OR live_item #>> '{estimateLineage,sources,0,unit}'
            <>COALESCE(live_item->>'unit','')
       OR (live_item->>'quantity')::numeric<>NEW.requested_quantity
       OR (
           EXISTS (
               SELECT 1 FROM public.supply_deliveries delivery
                WHERE delivery.request_id=NEW.request_id
                  AND delivery.material_name=
                      COALESCE(live_item->>'materialName',live_item->>'name','')
                  AND delivery.unit=COALESCE(live_item->>'unit','')
           )
           AND (
               SELECT COUNT(*)
                 FROM jsonb_array_elements(
                     CASE WHEN jsonb_typeof(live_items)='array'
                          THEN live_items ELSE '[]'::jsonb END
                 ) candidate
                WHERE COALESCE(candidate->>'materialName',candidate->>'name','')=
                      COALESCE(live_item->>'materialName',live_item->>'name','')
                  AND COALESCE(candidate->>'unit','')=
                      COALESCE(live_item->>'unit','')
           )<>1
       )
       OR (
           SELECT COUNT(*)
             FROM jsonb_array_elements(
                 CASE WHEN jsonb_typeof(live_items)='array'
                      THEN live_items ELSE '[]'::jsonb END
             ) candidate
             CROSS JOIN LATERAL jsonb_array_elements(
                 CASE WHEN jsonb_typeof(candidate #> '{estimateLineage,sources}')='array'
                      THEN candidate #> '{estimateLineage,sources}'
                      ELSE '[]'::jsonb END
             ) candidate_source
            WHERE (candidate_source->>'estimateId')::integer=NEW.source_estimate_id
              AND (candidate_source->>'sectionIndex')::integer=NEW.source_section_index
              AND (candidate_source->>'itemIndex')::integer=NEW.source_item_index
       )<>1
       OR NOT EXISTS (
           SELECT 1
             FROM public.estimate_row_transfer_entries entry
             JOIN public.estimate_row_transfer_plans plan
               ON plan.id=entry.plan_id
              AND plan.company_id=entry.company_id
              AND plan.project_id=entry.project_id
             JOIN public.estimate_versions source_version
               ON source_version.id=NEW.source_estimate_version_id
             JOIN public.estimate_versions target_version
               ON target_version.id=NEW.target_estimate_version_id
            WHERE entry.id=NEW.entry_id AND entry.plan_id=NEW.plan_id
              AND entry.company_id=NEW.company_id
              AND entry.project_id=NEW.project_id
              AND entry.source_kind='supply'
              AND entry.source_id=NEW.request_id
              AND entry.source_parent_id=NEW.request_id
              AND entry.request_item_index=NEW.request_item_index
              AND entry.source_estimate_id=NEW.source_estimate_id
              AND entry.source_estimate_version_id=NEW.source_estimate_version_id
              AND entry.source_section_index=NEW.source_section_index
              AND entry.source_item_index=NEW.source_item_index
              AND entry.source_item_key=NEW.source_item_key
              AND entry.source_sections_sha256=NEW.source_sections_sha256
              AND entry.target_estimate_id=NEW.target_estimate_id
              AND entry.target_estimate_version_id=NEW.target_estimate_version_id
              AND entry.target_section_index=NEW.target_section_index
              AND entry.target_item_index=NEW.target_item_index
              AND entry.target_item_key=NEW.target_item_key
              AND entry.target_sections_sha256=NEW.target_sections_sha256
              AND entry.source_total_quantity=NEW.requested_quantity
              AND entry.source_protected_quantity=
                  NEW.received_quantity+NEW.previously_allocated_quantity
              AND entry.source_available_quantity=
                  NEW.requested_quantity-NEW.received_quantity
                  -NEW.previously_allocated_quantity
              AND entry.quantity=NEW.allocation_quantity
              AND plan.reconciliation_id=NEW.reconciliation_id
              AND plan.status='approved' AND plan.plan_sha256=NEW.plan_sha256
              AND plan.approved_plan_sha256=NEW.plan_sha256
              AND plan.work_package=NEW.target_work_package
              AND plan.base_estimate_id=NEW.source_estimate_id
              AND plan.target_estimate_id=NEW.target_estimate_id
              AND source_version.estimate_id=NEW.source_estimate_id
              AND source_version.sections_sha256=NEW.source_sections_sha256
              AND source_version.sections_json::jsonb #>> ARRAY[
                    NEW.source_section_index::text,'items',
                    NEW.source_item_index::text,'name'
                  ]=COALESCE(live_item->>'materialName',live_item->>'name','')
              AND COALESCE(source_version.sections_json::jsonb #>> ARRAY[
                    NEW.source_section_index::text,'items',
                    NEW.source_item_index::text,'unit'
                  ],'шт')=COALESCE(live_item->>'unit','')
              AND target_version.estimate_id=NEW.target_estimate_id
              AND target_version.sections_sha256=NEW.target_sections_sha256
              AND target_version.sections_json::jsonb #>> ARRAY[
                    NEW.target_section_index::text,'items',
                    NEW.target_item_index::text,'name'
                  ]=NEW.target_material_name
              AND LOWER(BTRIM(COALESCE(
                    target_version.sections_json::jsonb #>> ARRAY[
                      NEW.target_section_index::text,'items',
                      NEW.target_item_index::text,'itemType'
                    ],
                    target_version.sections_json::jsonb #>> ARRAY[
                      NEW.target_section_index::text,'items',
                      NEW.target_item_index::text,'type'
                    ],''
                  ))) IN ('material','materials','материал','материалы')
              AND COALESCE(NULLIF(target_version.sections_json::jsonb #>> ARRAY[
                    NEW.target_section_index::text,'items',
                    NEW.target_item_index::text,'unit'
                  ],''),'шт')=NEW.target_unit
       ) THEN
        RAISE EXCEPTION 'estimate_row_supply_allocation_invalid'
          USING ERRCODE='23514';
    END IF;
    RETURN NEW;
END
$$
"""

CHANGE_DEFINITIONS = (
    ("create_plans_table", "plans_table", CREATE_PLANS_TABLE),
    ("create_entries_table", "entries_table", CREATE_ENTRIES_TABLE),
    ("create_owner_index", "idx_etrp_owner_created", """
        CREATE INDEX idx_etrp_owner_created
        ON public.estimate_row_transfer_plans(company_id,project_id,created_at DESC,id DESC)
    """),
    ("create_single_approved_index", "uq_etrp_single_approved", """
        CREATE UNIQUE INDEX uq_etrp_single_approved
        ON public.estimate_row_transfer_plans(company_id,reconciliation_id)
        WHERE status='approved'
    """),
    ("create_entry_plan_index", "idx_etre_plan", """
        CREATE INDEX idx_etre_plan ON public.estimate_row_transfer_entries(plan_id,id)
    """),
    ("create_assignment_source_index", "uq_etre_assignment_source", """
        CREATE UNIQUE INDEX uq_etre_assignment_source
        ON public.estimate_row_transfer_entries(plan_id,source_id)
        WHERE source_kind='assignment'
    """),
    ("create_supply_source_index", "uq_etre_supply_source", """
        CREATE UNIQUE INDEX uq_etre_supply_source
        ON public.estimate_row_transfer_entries(plan_id,source_id,request_item_index)
        WHERE source_kind='supply'
    """),
    ("create_entry_owner_index", "uq_etre_id_plan_owner", """
        CREATE UNIQUE INDEX uq_etre_id_plan_owner
        ON public.estimate_row_transfer_entries(id,plan_id,company_id,project_id)
    """),
    (
        "create_assignment_transfers_table",
        "assignment_transfers_table",
        CREATE_ASSIGNMENT_TRANSFERS_TABLE,
    ),
    (
        "create_supply_allocations_table",
        "supply_allocations_table",
        CREATE_SUPPLY_ALLOCATIONS_TABLE,
    ),
    ("create_assignment_transfer_plan_index", "idx_erat_plan", """
        CREATE INDEX idx_erat_plan
        ON public.estimate_row_assignment_transfers(plan_id,id)
    """),
    ("create_supply_allocation_plan_index", "idx_ersa_plan", """
        CREATE INDEX idx_ersa_plan
        ON public.estimate_row_supply_allocations(plan_id,id)
    """),
    ("create_supply_allocation_request_index", "idx_ersa_request_item", """
        CREATE INDEX idx_ersa_request_item
        ON public.estimate_row_supply_allocations(
            company_id,request_id,request_item_index,id
        )
    """),
    ("create_entry_guard_function", "reject_estimate_row_transfer_entry_mutation", ENTRY_GUARD_FUNCTION),
    ("create_plan_guard_function", "guard_estimate_row_transfer_plan_mutation", PLAN_GUARD_FUNCTION),
    (
        "create_assignment_transfer_guard_function",
        "guard_estimate_row_assignment_transfer",
        ASSIGNMENT_TRANSFER_GUARD_FUNCTION,
    ),
    (
        "create_supply_allocation_guard_function",
        "guard_estimate_row_supply_allocation",
        SUPPLY_ALLOCATION_GUARD_FUNCTION,
    ),
    ("create_entry_guard_trigger", "estimate_row_transfer_entry_immutable", """
        CREATE TRIGGER estimate_row_transfer_entry_immutable
        BEFORE UPDATE OR DELETE ON public.estimate_row_transfer_entries
        FOR EACH ROW EXECUTE FUNCTION public.reject_estimate_row_transfer_entry_mutation()
    """),
    ("create_plan_guard_trigger", "estimate_row_transfer_plan_guard", """
        CREATE TRIGGER estimate_row_transfer_plan_guard
        BEFORE UPDATE OR DELETE ON public.estimate_row_transfer_plans
        FOR EACH ROW EXECUTE FUNCTION public.guard_estimate_row_transfer_plan_mutation()
    """),
    (
        "create_assignment_transfer_guard_trigger",
        "estimate_row_assignment_transfer_guard",
        """
        CREATE TRIGGER estimate_row_assignment_transfer_guard
        BEFORE INSERT OR UPDATE OR DELETE
        ON public.estimate_row_assignment_transfers
        FOR EACH ROW EXECUTE FUNCTION public.guard_estimate_row_assignment_transfer()
        """,
    ),
    (
        "create_supply_allocation_guard_trigger",
        "estimate_row_supply_allocation_guard",
        """
        CREATE TRIGGER estimate_row_supply_allocation_guard
        BEFORE INSERT OR UPDATE OR DELETE
        ON public.estimate_row_supply_allocations
        FOR EACH ROW EXECUTE FUNCTION public.guard_estimate_row_supply_allocation()
        """,
    ),
)


def _values(catalog, key):
    return {str(value) for value in (catalog.get(key) or [])}


def _compact_definition(value):
    compact = re.sub(r'[\s"()]', "", str(value or "").lower())
    return compact.replace("public.", "")


def _invalid_definitions(present_names, definitions, signatures):
    definitions = dict(definitions or {})
    invalid = []
    for name, required_fragments in signatures.items():
        if name not in present_names:
            continue
        actual = _compact_definition(definitions.get(name))
        if not actual or any(
            _compact_definition(fragment) not in actual
            for fragment in required_fragments
        ):
            invalid.append(name)
    return invalid


def build_schema_plan(catalog):
    catalog = dict(catalog or {})
    plans_table = bool(catalog.get("plans_table"))
    entries_table = bool(catalog.get("entries_table"))
    assignment_transfers_table = bool(catalog.get("assignment_transfers_table"))
    supply_allocations_table = bool(catalog.get("supply_allocations_table"))
    blockers = []
    missing_plan_columns = sorted(PLAN_COLUMNS - _values(catalog, "plan_columns")) if plans_table else []
    missing_entry_columns = sorted(ENTRY_COLUMNS - _values(catalog, "entry_columns")) if entries_table else []
    missing_assignment_transfer_columns = (
        sorted(
            ASSIGNMENT_TRANSFER_COLUMNS
            - _values(catalog, "assignment_transfer_columns")
        )
        if assignment_transfers_table else []
    )
    missing_supply_allocation_columns = (
        sorted(
            SUPPLY_ALLOCATION_COLUMNS
            - _values(catalog, "supply_allocation_columns")
        )
        if supply_allocations_table else []
    )
    if (
        (entries_table and not plans_table)
        or (assignment_transfers_table and not (plans_table and entries_table))
        or (supply_allocations_table and not (plans_table and entries_table))
    ):
        blockers.append("table_dependency_invalid")
    constraints = _values(catalog, "constraints")
    if missing_plan_columns:
        blockers.append("plan_columns_invalid")
    if missing_entry_columns:
        blockers.append("entry_columns_invalid")
    if missing_assignment_transfer_columns:
        blockers.append("assignment_transfer_columns_invalid")
    if missing_supply_allocation_columns:
        blockers.append("supply_allocation_columns_invalid")
    if plans_table and not PLAN_CONSTRAINTS.issubset(constraints):
        blockers.append("plan_constraints_invalid")
    if entries_table and not ENTRY_CONSTRAINTS.issubset(constraints):
        blockers.append("entry_constraints_invalid")
    if (
        assignment_transfers_table
        and not ASSIGNMENT_TRANSFER_CONSTRAINTS.issubset(constraints)
    ):
        blockers.append("assignment_transfer_constraints_invalid")
    if (
        supply_allocations_table
        and not SUPPLY_ALLOCATION_CONSTRAINTS.issubset(constraints)
    ):
        blockers.append("supply_allocation_constraints_invalid")

    indexes = _values(catalog, "indexes")
    functions = _values(catalog, "functions")
    triggers = _values(catalog, "triggers")
    invalid_definitions = (
        ("invalidConstraint", _invalid_definitions(
            constraints, catalog.get("constraint_definitions"), CONSTRAINT_SIGNATURES,
        )),
        ("invalidIndex", _invalid_definitions(
            indexes, catalog.get("index_definitions"), INDEX_SIGNATURES,
        )),
        ("invalidFunction", _invalid_definitions(
            functions, catalog.get("function_definitions"), FUNCTION_SIGNATURES,
        )),
        ("invalidTrigger", _invalid_definitions(
            triggers, catalog.get("trigger_definitions"), TRIGGER_SIGNATURES,
        )),
    )
    for prefix, names in invalid_definitions:
        blockers.extend(f"{prefix}:{name}" for name in names)
    changes = []
    for name, object_name, sql in CHANGE_DEFINITIONS:
        if object_name == "plans_table":
            missing = not plans_table
        elif object_name == "entries_table":
            missing = not entries_table
        elif object_name == "assignment_transfers_table":
            missing = not assignment_transfers_table
        elif object_name == "supply_allocations_table":
            missing = not supply_allocations_table
        elif object_name in INDEXES:
            missing = object_name not in indexes
        elif object_name in FUNCTIONS:
            missing = object_name not in functions
        else:
            missing = object_name not in triggers
        if missing:
            changes.append({"name": name, "sql": sql.strip()})

    expected = {
        "planColumns": sorted(PLAN_COLUMNS),
        "entryColumns": sorted(ENTRY_COLUMNS),
        "assignmentTransferColumns": sorted(ASSIGNMENT_TRANSFER_COLUMNS),
        "supplyAllocationColumns": sorted(SUPPLY_ALLOCATION_COLUMNS),
        "constraints": sorted(
            PLAN_CONSTRAINTS
            | ENTRY_CONSTRAINTS
            | ASSIGNMENT_TRANSFER_CONSTRAINTS
            | SUPPLY_ALLOCATION_CONSTRAINTS
        ),
        "indexes": sorted(INDEXES),
        "functions": sorted(FUNCTIONS),
        "triggers": sorted(TRIGGERS),
        "constraintDefinitions": {
            name: " ".join(fragments)
            for name, fragments in sorted(CONSTRAINT_SIGNATURES.items())
        },
        "indexDefinitions": {
            name: " ".join(fragments)
            for name, fragments in sorted(INDEX_SIGNATURES.items())
        },
        "functionDefinitions": {
            name: " ".join(fragments)
            for name, fragments in sorted(FUNCTION_SIGNATURES.items())
        },
        "triggerDefinitions": {
            name: " ".join(fragments)
            for name, fragments in sorted(TRIGGER_SIGNATURES.items())
        },
    }
    return {
        "schemaReady": not blockers and not changes,
        "readyForApply": not blockers,
        "blockers": blockers,
        "missingPlanColumns": missing_plan_columns,
        "missingEntryColumns": missing_entry_columns,
        "missingAssignmentTransferColumns": missing_assignment_transfer_columns,
        "missingSupplyAllocationColumns": missing_supply_allocation_columns,
        "changes": changes,
        "expected": expected,
    }


def schema_plan_sha256(changes):
    normalized = [
        {"name": item["name"], "sql": " ".join(item["sql"].split())}
        for item in changes or []
    ]
    payload = json.dumps(normalized, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _load_catalog(cur):
    cur.execute("""
        SELECT
          to_regclass('public.estimate_row_transfer_plans') IS NOT NULL AS plans_table,
          to_regclass('public.estimate_row_transfer_entries') IS NOT NULL AS entries_table,
          to_regclass('public.estimate_row_assignment_transfers') IS NOT NULL
            AS assignment_transfers_table,
          to_regclass('public.estimate_row_supply_allocations') IS NOT NULL
            AS supply_allocations_table,
          COALESCE((SELECT array_agg(a.attname::text ORDER BY a.attname)
            FROM pg_attribute a JOIN pg_class c ON c.oid=a.attrelid
            JOIN pg_namespace n ON n.oid=c.relnamespace
           WHERE n.nspname='public' AND c.relname='estimate_row_transfer_plans'
             AND a.attnum>0 AND NOT a.attisdropped),ARRAY[]::text[])
            AS plan_columns,
          COALESCE((SELECT array_agg(a.attname::text ORDER BY a.attname)
            FROM pg_attribute a JOIN pg_class c ON c.oid=a.attrelid
            JOIN pg_namespace n ON n.oid=c.relnamespace
           WHERE n.nspname='public' AND c.relname='estimate_row_transfer_entries'
             AND a.attnum>0 AND NOT a.attisdropped),ARRAY[]::text[])
            AS entry_columns,
          COALESCE((SELECT array_agg(a.attname::text ORDER BY a.attname)
            FROM pg_attribute a JOIN pg_class c ON c.oid=a.attrelid
            JOIN pg_namespace n ON n.oid=c.relnamespace
           WHERE n.nspname='public'
             AND c.relname='estimate_row_assignment_transfers'
             AND a.attnum>0 AND NOT a.attisdropped),ARRAY[]::text[])
            AS assignment_transfer_columns,
          COALESCE((SELECT array_agg(a.attname::text ORDER BY a.attname)
            FROM pg_attribute a JOIN pg_class c ON c.oid=a.attrelid
            JOIN pg_namespace n ON n.oid=c.relnamespace
           WHERE n.nspname='public'
             AND c.relname='estimate_row_supply_allocations'
             AND a.attnum>0 AND NOT a.attisdropped),ARRAY[]::text[])
            AS supply_allocation_columns,
          COALESCE((SELECT array_agg(c.conname ORDER BY c.conname)
            FROM pg_constraint c JOIN pg_class t ON t.oid=c.conrelid
            JOIN pg_namespace n ON n.oid=t.relnamespace
           WHERE n.nspname='public' AND t.relname IN
             ('estimate_row_transfer_plans','estimate_row_transfer_entries',
              'estimate_row_assignment_transfers',
              'estimate_row_supply_allocations')),ARRAY[]::text[])
            AS constraints,
          COALESCE((SELECT jsonb_object_agg(c.conname,pg_get_constraintdef(c.oid,true))
            FROM pg_constraint c JOIN pg_class t ON t.oid=c.conrelid
            JOIN pg_namespace n ON n.oid=t.relnamespace
           WHERE n.nspname='public' AND t.relname IN
             ('estimate_row_transfer_plans','estimate_row_transfer_entries',
              'estimate_row_assignment_transfers',
              'estimate_row_supply_allocations')),'{}'::jsonb)
            AS constraint_definitions,
          COALESCE((SELECT array_agg(indexname ORDER BY indexname)
            FROM pg_indexes WHERE schemaname='public' AND tablename IN
             ('estimate_row_transfer_plans','estimate_row_transfer_entries',
              'estimate_row_assignment_transfers',
              'estimate_row_supply_allocations')),ARRAY[]::text[])
            AS indexes,
          COALESCE((SELECT jsonb_object_agg(indexname,indexdef)
            FROM pg_indexes WHERE schemaname='public' AND tablename IN
             ('estimate_row_transfer_plans','estimate_row_transfer_entries',
              'estimate_row_assignment_transfers',
              'estimate_row_supply_allocations')),'{}'::jsonb)
            AS index_definitions,
          COALESCE((SELECT array_agg(p.proname ORDER BY p.proname)
            FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
           WHERE n.nspname='public' AND p.proname IN
             ('reject_estimate_row_transfer_entry_mutation',
              'guard_estimate_row_transfer_plan_mutation',
              'guard_estimate_row_assignment_transfer',
              'guard_estimate_row_supply_allocation') AND p.pronargs=0),ARRAY[]::text[])
            AS functions,
          COALESCE((SELECT jsonb_object_agg(p.proname,pg_get_functiondef(p.oid))
            FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
           WHERE n.nspname='public' AND p.proname IN
             ('reject_estimate_row_transfer_entry_mutation',
              'guard_estimate_row_transfer_plan_mutation',
              'guard_estimate_row_assignment_transfer',
              'guard_estimate_row_supply_allocation') AND p.pronargs=0),'{}'::jsonb)
            AS function_definitions,
          COALESCE((SELECT array_agg(tg.tgname ORDER BY tg.tgname)
            FROM pg_trigger tg JOIN pg_class c ON c.oid=tg.tgrelid
            JOIN pg_namespace n ON n.oid=c.relnamespace
           WHERE n.nspname='public' AND NOT tg.tgisinternal AND tg.tgname IN
             ('estimate_row_transfer_entry_immutable',
              'estimate_row_transfer_plan_guard',
              'estimate_row_assignment_transfer_guard',
              'estimate_row_supply_allocation_guard')),ARRAY[]::text[])
            AS triggers,
          COALESCE((SELECT jsonb_object_agg(tg.tgname,pg_get_triggerdef(tg.oid,true))
            FROM pg_trigger tg JOIN pg_class c ON c.oid=tg.tgrelid
            JOIN pg_namespace n ON n.oid=c.relnamespace
           WHERE n.nspname='public' AND NOT tg.tgisinternal AND tg.tgname IN
             ('estimate_row_transfer_entry_immutable',
              'estimate_row_transfer_plan_guard',
              'estimate_row_assignment_transfer_guard',
              'estimate_row_supply_allocation_guard')),'{}'::jsonb)
            AS trigger_definitions
    """)
    return dict(cur.fetchone() or {})


def run_schema_migration(
    get_db,
    *,
    apply=False,
    expected_change_count=None,
    expected_plan_sha256=None,
):
    if apply:
        if (
            isinstance(expected_change_count, bool)
            or not isinstance(expected_change_count, int)
            or expected_change_count < 0
            or not PLAN_SHA256_RE.fullmatch(str(expected_plan_sha256 or ""))
        ):
            raise SchemaMigrationError("schema_apply_guard_invalid")
    conn = get_db()
    cur = None
    try:
        conn.set_session(autocommit=False, isolation_level="SERIALIZABLE")
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SET LOCAL lock_timeout='5s'")
        cur.execute("SET LOCAL statement_timeout='30s'")
        if apply:
            cur.execute("SELECT pg_advisory_xact_lock(8242002)")
        before = build_schema_plan(_load_catalog(cur))
        plan_hash = schema_plan_sha256(before["changes"])
        if not before["readyForApply"]:
            raise SchemaMigrationError("schema_catalog_blocked")
        if apply and (
            expected_change_count != len(before["changes"])
            or expected_plan_sha256 != plan_hash
        ):
            raise SchemaMigrationError("schema_apply_guard_mismatch")

        if not apply:
            conn.rollback()
            return {
                "ok": True,
                "dryRun": True,
                "rolledBack": True,
                "committed": False,
                "writesAttempted": 0,
                "schemaReady": before["schemaReady"],
                "readyForApply": before["readyForApply"],
                "blockers": before["blockers"],
                "changeCount": len(before["changes"]),
                "changes": [item["name"] for item in before["changes"]],
                "planSha256": plan_hash,
            }

        writes_attempted = 0
        for change in before["changes"]:
            cur.execute(change["sql"])
            writes_attempted += 1
        after = build_schema_plan(_load_catalog(cur))
        if not after["schemaReady"]:
            raise SchemaMigrationError(
                "schema_postcheck_failed:"
                + json.dumps({
                    "blockers": after["blockers"],
                    "missingPlanColumns": after["missingPlanColumns"],
                    "missingEntryColumns": after["missingEntryColumns"],
                    "missingAssignmentTransferColumns": after[
                        "missingAssignmentTransferColumns"
                    ],
                    "missingSupplyAllocationColumns": after[
                        "missingSupplyAllocationColumns"
                    ],
                    "changes": [item["name"] for item in after["changes"]],
                }, sort_keys=True)
            )
        conn.commit()
        return {
            "ok": True,
            "dryRun": False,
            "rolledBack": False,
            "committed": True,
            "writesAttempted": writes_attempted,
            "schemaReady": True,
            "readyForApply": True,
            "blockers": [],
            "changeCount": len(before["changes"]),
            "changes": [item["name"] for item in before["changes"]],
            "planSha256": plan_hash,
        }
    except Exception:
        conn.rollback()
        raise
    finally:
        if cur is not None:
            cur.close()
        conn.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description="Guarded E4 transfer ledger schema migration")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--expected-change-count", type=int)
    parser.add_argument("--expected-plan-sha256")
    args = parser.parse_args(argv)
    if not args.apply and (
        args.expected_change_count is not None or args.expected_plan_sha256 is not None
    ):
        parser.error("apply guards are valid only with --apply")
    if args.apply and (
        args.expected_change_count is None or args.expected_plan_sha256 is None
    ):
        parser.error("--apply requires exact change count and plan SHA-256")
    try:
        from backend.db import get_db
    except ModuleNotFoundError:
        from db import get_db
    report = run_schema_migration(
        get_db,
        apply=args.apply,
        expected_change_count=args.expected_change_count,
        expected_plan_sha256=args.expected_plan_sha256,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
