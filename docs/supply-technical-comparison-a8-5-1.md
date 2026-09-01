# A8.5.1 — Deterministic supply technical matcher

## Purpose

This slice adds a pure technical comparison kernel for supplier quotations. It
is designed for shadow-mode analysis and does not register an API route, queue
handler, model call, database query or business writer.

The kernel answers two separate questions:

1. Are two supplier quotations technically comparable for one canonical
   requested material?
2. Does one offered line satisfy one requested material line without a detected
   engineering conflict?

## Safety boundary

The implementation is deliberately fail-closed:

- fuzzy text similarity never overrides a hard technical conflict;
- missing required attributes lead to `review_required`;
- every public result reports `automaticApprovalAllowed=false`;
- every public result reports `writesAttempted=0` and `modelCalls=0`;
- hashes are deterministic and bind the normalized technical evidence to the
  returned decision;
- all quantity and money aggregation uses `Decimal`;
- packaging units are never silently converted to pieces;
- different manufacturers, SKUs or work packages are not merged automatically.

## Decisions

The integration-safe decision vocabulary is:

- `exact` — the normalized names and units match;
- `comparable` — a deterministic engineering signature matches, but this still
  does not authorize approval;
- `review_required` — evidence is missing, ambiguous or model-sensitive;
- `incompatible` — a hard engineering conflict was detected.

For compatibility with the v0.9 Kislovodsk calibration, pair results also expose
legacy statuses `ok`, `review` and `blocked`.

## Detected technical evidence

The first version recognizes and compares:

- product family;
- dimensions;
- nominal and outside diameters;
- thread sizes;
- internal/external thread gender, including multiplicity;
- 45° and 90° angles;
- PN/Ru pressure class;
- SDR;
- fibre, aluminium and explicit unreinforced pipe variants;
- horizontal, vertical, straight and angled designs;
- dry siphon, eccentric transition and sewer application markers;
- package/weight markers.

## Split-line aggregation

`aggregate_supply_lines()` combines only lines with the same conservative key:

- normalized name;
- technical signature;
- base unit;
- SKU;
- manufacturer;
- work package.

For example, 100 m and 70 m of the same line become 170 m. The resulting unit
price is `sum(total) / sum(quantity)`, not an average of the two unit prices.

Safe explicit conversions currently include tonnes/grams to kilograms and
centimetres/millimetres to metres. Package conversion factors remain outside
this slice and require authoritative product data.

## Benchmark gate

`run_technical_benchmark()` reports:

- total and correct cases;
- accuracy in basis points;
- false-safe count (`review` or `blocked` predicted as `ok`);
- dangerous-error count (`blocked` predicted as `ok`);
- confusion matrix;
- deterministic result hashes.

The historical Kislovodsk set remains a calibration set, not an independent
holdout. The next slice must freeze previously unseen documents before tuning
rules against them.

## Local validation performed for this patch

- focused unit tests: 27 passed;
- compilation: passed;
- Kislovodsk calibration: 66/66 classifications reproduced;
- false-safe calibration errors: 0;
- dangerous calibration errors: 0.

These numbers show compatibility with the existing calibration only. They do
not establish production accuracy.

## Next integration slice

A8.5.2 should add one read-only source resolver that obtains a selected request,
supplier offer/invoice and protected file under one exact company/project scope.
It should call this pure kernel and roll back the database transaction before
returning. No ranking, supplier selection, invoice approval, RFQ sending,
payment, warehouse mutation or estimate mutation belongs in A8.5.2.
