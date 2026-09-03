# A8.5.4 — Read-only comparison inside the supply offer card

## Outcome

A8.5.4 adds one explicit **«Проверить характеристики»** action to the existing
supplier-offer card. It does not add another supply page or workflow. The
action presents the deterministic A8.5.3 result next to the source PDF so the
supply employee can see whether the requested and offered nomenclature are an
exact match, technically comparable, in need of review, or incompatible.

The panel cannot rank or select a supplier, approve an invoice, initiate a
payment, mutate a request, or call a model. Its visible explanation states
that it is only a check and that the employee retains the decision.

## Exact UI boundary

The action is rendered only when all of these facts are exact:

- the frontend build flag is exactly `true`;
- the selected company is in the exact frontend company allowlist;
- company mode is exactly `company`;
- the selected-company role is `директор`, `зам_директора` or `снабженец`;
- one project in the selected company has the request's exact project name;
- request and supplier-offer IDs are positive safe integers;
- the offer PDF reference is exactly `/tenant-files/{fileId}/content`.

Missing, duplicate, cross-company or malformed selectors hide the action and
produce no request. The panel never infers a project or file from a partial
name, public URL or object-storage address.

## Explicit read

No comparison is loaded while rendering the supply list. One click makes one
cookie-authenticated, `no-store` GET request:

```text
GET /supply-requests/{requestId}/technical-comparisons/supplier_offer/{offerId}?projectId={projectId}&fileId={fileId}
```

The response is accepted only when its selectors match the current UI scope,
its closed field shapes are valid, and it proves:

- `dryRun=true`;
- `readOnlyTransaction=true`;
- `rolledBack=true`;
- `writesAttempted=0`;
- `modelCalls=0`;
- `automaticApprovalAllowed=false`.

An invalid or stale response is discarded. Changing company or source aborts
an in-flight read and clears the previous result.

## Default-off frontend canary

Both build settings are required:

```text
REACT_APP_SUPPLY_TECHNICAL_COMPARISON_ENABLED=true
REACT_APP_SUPPLY_TECHNICAL_COMPARISON_COMPANY_IDS=1
```

They must be enabled only together with the A8.5.3 backend and Nginx canary:

```text
SUPPLY_TECHNICAL_COMPARISON_HTTP_ENABLED=true
SUPPLY_TECHNICAL_COMPARISON_COMPANY_IDS=1
```

Without the frontend settings, production behavior and the existing supplier
offer controls remain unchanged.

## Verification

The focused UI tests prove default-closed visibility, exact selector
derivation, explicit loading only, closed response validation, stale-scope
discarding, and absence of selection, approval and payment actions from the
comparison panel.
