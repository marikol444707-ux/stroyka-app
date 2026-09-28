# Deployment retention

The user explicitly requires deleting deployment backups and staging after an
update is successfully installed and verified. Do not accumulate release copies.
Follow docs/deployment-retention.md. Keep rollback files only while deployment is
unfinished or failed. Back up only the current frontend manifest and public files,
not historical static chunks; do not create a full Git bundle backup per release.
Never depend on an old staging directory surviving cleanup. Completed releases
must emit deployed.json only after all release checks pass. The installed
stroyka-release-cleanup timer finalizes eligible stages automatically.

Before cleanup, separately verify backend, database, frontend files and the browser
workflow. Only then write verified.json matching the release head with all four
checks true (see docs/deployment-retention.md). Deployment completion or a passing
health endpoint alone is insufficient. Missing/failed verification retains backups.

# Company documents and requisites (user-approved rules)

- Follow tasks/counterparty-documents-plan.md and tasks/requisites-autofill-matrix.md.
- Keep every company's archive isolated, including companies under one owner.
  Authorize metadata, mutations, downloads and exports on the server. Never infer
  ownership from names; unassigned legacy records remain inaccessible.
- Settings requisites are the canonical confirmed company profile. Settings legal
  documents and the company archive must reference the same originals, not copies.
- Autofill new drafts from authorized parties and confirmed sources. OCR is a
  suggestion requiring review; never overwrite manual edits or invent missing data.
- Buyer equals payer for new deals, enforced server-side. Preserve historical
  differing parties. Delivery recipient/address is independent of payer identity.
- Reuse a checked contract/version across eligible deals between the same parties;
  do not require re-upload or OCR for each quotation.
- Freeze party, bank and authorized signer data when issuing/approving documents.
  Reprints and exports use the saved snapshot, never today's mutable profile.
- Show conflicting contract/profile bank details before preparing a new payment;
  do not silently switch accounts. File uploads must not post payments or stock.
- Share only explicitly addressed document versions. Supplier/customer cabinets
  must not expose the other company's entire archive or internal purchase data.
- Completion requires cross-company, profile-change/reprint, manual-edit and
  end-to-end tests from the matrix. A written plan is not proof of implementation.
