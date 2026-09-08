# A8.5.2 — supply request workflow E2E smoke

The protected smoke script is `scripts/smoke-supply-request-workflow.py`.
It is intentionally not part of ordinary CI because it creates short-lived
records in the selected deployed environment.

## Covered path with a project reviewer

1. A temporary master creates a `Новая` request from an active estimate item.
2. The master cannot confirm the request.
3. Leadership cannot use the fallback while an active foreman is assigned.
4. Supply cannot dispatch the request before approval.
5. The assigned foreman confirms it.
6. A director approves it.
7. A supply specialist dispatches it to one supplier.
8. Only that supplier sees the supplier-safe request and answers the RFQ.
9. Supply sees the received offer.

## Covered fallback path

1. The temporary foreman is deactivated and the script proves that no active
   project reviewer remains.
2. A master creates another request.
3. A director performs the separate fallback confirmation.
4. Dispatch is still blocked until the director performs the second,
   explicit approval action.
5. Supply dispatches the approved request and the same supplier isolation
   checks run again.

## Guard and cleanup

Privileged temporary users complete the backend-required initial
2FA setup through `/login/2fa/setup-confirm`. The setup secret is not
printed. Cleanup revokes temporary sessions, clears temporary 2FA
secrets and disables all temporary users.

Temporary fixture assignments and runtime project-access names are
trimmed before comparison. This preserves access to legacy projects whose
stored names contain accidental leading or trailing whitespace.

The script refuses to run without the exact phrase:

```text
RUN SUPPLY WORKFLOW SMOKE
```

Example after the branch is deployed:

```bash
cd /var/www/stroyka-app
PYTHONPATH=. python3 scripts/smoke-supply-request-workflow.py \
  --confirm 'RUN SUPPLY WORKFLOW SMOKE'
```

Optional environment overrides:

- `BASE_URL`
- `SUPPLY_WORKFLOW_SMOKE_COMPANY_ID`
- `SUPPLY_WORKFLOW_SMOKE_PROJECT_ID`

The selected project must have an active estimate and no pre-existing active
assigned foreman or chief engineer. The script creates a temporary foreman for
the ordinary path, deactivates that account for the fallback path, removes the
created requests, offers, recipients and supplier cards, and disables all
created temporary users in a `finally` cleanup.


## Legacy project identity during RFQ dispatch

`supply_requests` currently stores the company and project name but not a
`project_id`. RFQ dispatch therefore resolves a legacy project inside the
stored request company by a trimmed name comparison. The lookup remains
fail-closed: exactly one non-archived project must match. Zero matches and
normalized-name duplicates continue to return HTTP 409.

This compatibility lookup does not rename production projects and does not
replace a future migration to exact `project_id` ownership.
