"""Persistent company/supplier/version denials shared by every contract reader."""


def contract_access_filter(alias='v'):
    if alias not in ('v','c'):
        raise ValueError('Unknown contract alias')
    return f"""NOT EXISTS (SELECT 1 FROM company_supplier_links closed_contract_link
        WHERE closed_contract_link.company_id={alias}.company_id
          AND closed_contract_link.supplier_id::text={alias}.snapshot_json #>> '{{supplier,supplierId}}'
          AND COALESCE(to_jsonb(closed_contract_link)->'profile'->'closedContractVersionIds','[]'::jsonb)
              @> jsonb_build_array({alias}.id))"""
