# Contract recognition rollout

Automatic recognition follows original upload in contract review. Recognized
requisites fill only empty fields for a party whose extracted INN matches the
selected identity. Existing names/INNs remain from selected company context.
Manual edits are retained. Replacing an original clears unchanged autofilled
fields; failure retains the new original and displays a readable explanation.
Saving still requires explicit human confirmation; accepted unchanged recognized
fields carry server-rechecked content hash, line and quote provenance.

Formats: TXT, text PDF, scanned/image-bearing PDF, PNG/JPEG, DOCX and DOC.
Text DOCX is read directly; image/object/header-bearing Word is rendered through
LibreOffice then processed page-by-page. Scans use Tesseract rus+eng. Linux worker
runs in bubblewrap with no network, a private writable directory, no application
credentials/files, and read-only system binaries/configuration. Parent enforces
120s timeout and cleans temporary data even on timeout. Bounds: 10MiB, 30 PDF
pages, 64000 characters, worker CPU/memory/file-size and DOCX expansion limits.

Dependencies installed: bubblewrap, tesseract-ocr plus rus/eng data,
libreoffice-writer, existing poppler/pdftoppm, pinned pypdf6.18.1. The sandbox
includes /bin symlink and LibreOffice registry config; real DOC conversion failed
without them and passed after correction.

Flags: SUPPLIER_CONTRACT_RECOGNITION_ENABLED=1 and
SUPPLIER_CONTRACT_DOCUMENT_READER_ENABLED=1. Build resolver exports recognition
UI flag and verifies deal-party/contract dependencies. No DB migration.

Verification: 19 frontend tests, 41 extraction/PDF/source tests plus added Word
source/hash regression (10 source tests), 11 build resolver tests passed.
Linux real fixtures passed text PDF, scanned PDF, PNG, DOCX and DOC. Headed browser
against disposable real API/database uploaded TXT, autofilled bank/BIK/signatory,
saved contract, and database confirmed original line/quote provenance. No real
contract was used or confirmed. Production rollout checks remain separate.

Limits: conservative explicit labelled requisites blocks only. Arbitrary layouts
may yield no suggestions; number/date/payment terms are still manual. OCR is not
proof of legal accuracy and never confirms/signs a contract. JPEG uses the same
OCR path as PNG but has not yet had a separate real-format check.
