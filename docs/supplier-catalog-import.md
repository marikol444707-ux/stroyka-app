# Supplier catalogue import

Scope: supplier cabinet Excel/XLS/UTF-8 CSV uploads and the existing price-link import.
The six columns remain name, unit, price, minimum quantity, delivery days, notes.
First row must be a recognized header; malformed files never silently lose their first item.
Preview validates every nonempty row before any write. Limits: 5 MiB and 500 data rows.
Comma decimals and grouped spaces are accepted; price >= 0, minimum > 0,
delivery days a nonnegative integer (including zero). Defaults only for empty cells.
Duplicates match trimmed, whitespace-normalized case-insensitive name + unit within
one supplier. Existing rows are skipped, never overwritten. Recheck current catalogue
before every import attempt. This is repeated-file protection in this UI, not a database
uniqueness guarantee against concurrent imports from different sessions.

Only successful POST replies with valid IDs enter local state. Stop on first error,
show confirmed count and failed file row. An ambiguous response requires checking the
current catalogue before another attempt; no automatic POST retries. UI locks while
reading/writing. Both entry points share the same preview and persistence path.
Invoices/payments and schema are outside this change. GET catalogue serialization
is corrected to preserve deliveryDays=0 instead of replacing it with the default 3.

## Verification

- Reproduced old import appending an HTTP403 row to local catalogue (RED), then GREEN.
- Reproduced initial supplier boot never setting the linked supplier card (RED).
  Initial load now fetches the authenticated supplier's cards and catalogue.
- Reproduced GET changing stored deliveryDays=0 to 3, then GREEN.
- Full frontend after the boot fix: 178 suites / 1116 tests passed.
  The final CSV parsing regression and loader/import tests: 44 tests passed.
- Backend discovery: 3765 tests, 639 explicit opt-in skips, no failures.
- Independent review: header positions, unit length and database INT bounds fixed;
  text NUL rejected before writes. No Critical/Required issues in importer review.
- Production build passed; browser acceptance and release evidence follows below.

## Browser acceptance (synthetic database only)

- Normal login loads the linked card without a special page URL.
- Real XLSX with comma price saved 2 rows, GET preserved price1234.5 and days0.
- Same file again: 0 new rows, 2 duplicates; invalid price blocks writes.
- Dropped response after the server committed: UI confirmed0, stopped remaining
  writes; explicit retry fetched current catalogue, skipped committed row and saved
  the remaining row once.
- 320px viewport/document width320, file input stays within the form; screenshot inspected.
- Fixture's supplier originally had no company: existing subscription guard rejected
  POST403 and UI correctly displayed zero saves. Success tests used a synthetic
  supplier assigned to fixture company2 with an active membership. This release does
  not bypass account/company/subscription requirements.
- Console: existing fixture online403/preload warnings and intentionally aborted
  import request; no importer exception.
- Real CSV regression: UTF-8 names and comma decimals survive SheetJS without
  implicit numeric coercion.
