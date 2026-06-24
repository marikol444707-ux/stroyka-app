# YandexGPT tuning dataset for Stroyka

This folder contains a seed dataset for Yandex AI Studio fine-tuning and evaluation.
It is intentionally focused on text-to-JSON behavior for Stroyka workflows, not on
teaching the model a hidden knowledge base.

## Current model roles in the app

- `qwen3.6-35b-a3b/latest` - best current fit for invoice/photo recognition and image input.
- `yandexgpt-5.1/latest` - structured text extraction, fallback reasoning, and production text tasks.
- `yandexgpt-5-lite` or fine-tuned `yandexgpt-lite/latest@...` - candidate for cheaper repeated text-to-JSON classification after we prove quality.
- `t-tech/T-pro-it-2.0-FP8` - optional self-hosted/OpenAI-compatible text model experiment. Do not replace OCR/photo flows with it unless we add a separate vision model.

## Files

- `stroyka_text2json_seed.jsonl` - training seed examples in Yandex `TextToTextGeneration` format.
- `stroyka_eval_holdout.jsonl` - holdout examples for quality checks. Do not train on these.

## What this dataset improves

- Routing a scanned invoice to warehouse, object warehouse, own expenses, or manual review.
- Extracting VAT, totals, invoice numbers, dates, suppliers, and multi-page document structure.
- Normalizing estimate rows such as `100 м2` into working units.
- Excluding negative estimate material rows from material control, requests, balances, and write-offs.
- Matching incoming material names to estimate materials through aliases.
- Classifying work vs material without forcing a user to pick everything manually.
- Returning low-confidence decisions as `needs_review` instead of writing bad data.
- Keeping role restrictions: workers and subcontractors see only their project/package.
- Protecting destructive actions: no AI auto-delete or auto-archive.

## Hard rules for adding new examples

- Use anonymized/synthetic data only. Do not include passports, real phone numbers, API keys, tokens, bank secrets, or full private invoices.
- Keep the same `system` instruction in every training row and in production calls to the fine-tuned model.
- Use exact JSON in `response`. If confidence is weak, return `status: "needs_review"`.
- Store bad model answers separately as negative/eval cases before adding a corrected training example.
- Keep OCR image tasks outside this text dataset. For images, first run OCR/vision, then pass extracted text here.

## Suggested production integration

Add a small model router instead of replacing every model at once:

```text
invoice_image_ocr      -> qwen3.6-35b-a3b/latest
invoice_text_structure -> tuned yandexgpt-lite/latest@... or yandexgpt-5.1/latest fallback
estimate_text_parse    -> tuned yandexgpt-lite/latest@... or yandexgpt-5.1/latest fallback
director_agent         -> yandexgpt-5-lite or yandexgpt-5.1/latest
cheap_batch_checks     -> tuned yandexgpt-lite/latest@...
experimental_local     -> T-pro-it-2.0-FP8 behind a feature flag
```

## Minimal acceptance checks

- Invoice selected as warehouse must not be saved as `own_expense`.
- Multi-page invoices must merge into one document and keep all source photo IDs.
- Negative estimate materials must not create supply demand.
- Material aliases must never auto-match below the confidence threshold.
- The model must return valid JSON only.
