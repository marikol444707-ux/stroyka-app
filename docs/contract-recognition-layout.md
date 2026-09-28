# Contract recognition and review — 28 September 2026

The review reads separately headed requisites columns and suggests OGRN, legal
address, bank, contacts and named signatory/basis in addition to numeric accounts.
Columns must contain exactly one INN/KPP pair matching the selected party.
Multiple identities/conflicting blocks are withheld. A payer is never inferred.
The preamble signer is associated by quoted company name AND explicit role.
Spelling and grammatical case remain as recognized; users must verify them.
Source quotes can span several original OCR lines and are verified again at save.
No company profile, payment, invoice or stock record is changed by recognition.

The form groups organization, bank and signatory/contact fields under party tabs.
It shows recognized values and source quotes, supports retry without another
upload, preserves manual edits, and offers explicit buyer-to-payer copying only
when both selected INNs match. Switching parties clears recognition and the file
selection to prevent reuse of evidence from an earlier context.

## Runtime

Existing isolated worker/flags remain in effect. PDF rendering uses 3200 px;
only geometrically aligned, distinct supplier/buyer headers permit column OCR.
Russian preambles use Russian recognition; labelled email rows use English OCR.
The process remains offline, bounded to 120 seconds, 30 pages, 10 MiB, 64000 chars.

Install the optional pinned accurate models with:

    bash scripts/install-contract-ocr-models.sh

Upstream: https://github.com/tesseract-ocr/tessdata_best
Pinned revision e12c65a915945e4c28e237a9b52bc4a8f39a0cec; SHA256 checked by installer.
Models/license live under /usr/local/share/stroyka-tessdata-best, visible read-only
inside the existing sandbox. They are runtime dependencies, not release backups.
Missing models use the packaged defaults. Pillow is required for column cropping
(already installed in this deployment). Documents are never uploaded to an OCR API.

## Validation

Synthetic column tests cover multiline provenance, postal/legal separation,
unknown/duplicate identities, role/company agreement, and geometry safeguards.
Real local PostgreSQL tests verify authenticated recognition and saved provenance.
Browser fixture exercises upload, tab/copy flow, checked save; 390 px dark and
1280 px light layouts have no horizontal overflow. Synthetic review creates no
invoice. The supplied seven-page scanned PDF is tested privately on the server;
remaining OCR letter errors require original-document review. No customer PDF,
requisites or extracted text is committed to the repository.
