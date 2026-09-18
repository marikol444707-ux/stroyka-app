# Journal company and project isolation

Production base: `51990a0a`; working branch: `codex/journal-isolation`.
Scope: material inspection and cable journals, their receipt writers, historical
ownership review and browser consumers. Supplier invoices/payments business
logic belongs to the other chat and is excluded.

- [x] Inspect deployed routes and unreleased ownership implementation.
- [x] Refresh the read-only production ownership inventory.
- [x] Extract additive ownership/review migrations without warehouse distribution
      or payment migrations; rehearse preserving every existing field.
- [x] Integrate exact company/project access, immutable owners and reviewed history.
- [x] Integrate receipt writers and verify partial receipts, retries and rollback.
- [x] Verify UI scope, exports and cross-company rejection in automated tests.
- [x] Run focused PostgreSQL and repository regression checks.
- [x] Publish only the independently verified release scope.
- [x] Verify both live journal views and complete print previews; correct the
      project-page company/user context wiring and cover it with a regression test.

Historical ownership is not inferred from a project name or a default company.
Human confirmation must refer to a concrete inventory. Unresolved records must
remain available through an authorized review path before strict reads activate.
The two earlier journal correctness/performance fixes must remain intact.

Owner explicitly confirmed in this conversation that all 340 inspections and
19 cable records belong to company 1, project 1, Кисловодск Лицей 4.
The release uses an operator-only, hash-pinned bootstrap with append-only audit.
It does not impersonate a director or claim a primary-document quality review.
Historical duplicate lines and non-metre cable values remain unchanged.
The rehearsed batch also binds exactly 45 referenced object warehouse invoices.
All original columns in all 143 copied production tables remain unchanged.

Production is `1cd73516c809` as of 18 September 2026, 22:11:41 MSK. Migration
`0023_quality_journal_owners` and the confirmed owner batch are applied.
Final browser counts and previews are 340 / 19; foreign-company HTTP reads are
403. See `docs/journal-isolation-2026-09-18.md` for checks and recovery evidence.
