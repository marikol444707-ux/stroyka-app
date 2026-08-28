# A14: Provider-neutral model gateway

## Objective

Create one backend boundary for model calls so business features no longer
construct provider clients, provider URLs, model URIs or fallback chains.
The existing Yandex cloud models remain the only production provider during
the migration. A local model is evaluated only after comparable quality,
latency, load and cost measurements exist.

This is an internal reliability refactor. It must not add a user-facing flow,
change prompts or response shapes, mutate business data, or enable a new
provider by configuration alone.

## Current inventory

The current tree contains 20 logical provider capabilities implemented across
30 direct-access functions, including nested transport helpers:

- 25 functions in `backend/main.py`, including one legacy direct Yandex
  Foundation Models HTTP call, OpenAI-compatible Yandex flows, their nested
  transport helpers and three cooperating invoice-scan functions;
- one each in `backend/features/estimate_changes/routes.py`,
  `backend/features/project_records/routes.py`,
  `backend/features/document_recognition/routes.py` and
  `backend/features/platform_admin/routes.py`; the estimate-change module also
  contains one nested transport helper.

Provider-specific details currently repeated in business code include
`YANDEX_API_KEY`, `YANDEX_FOLDER_ID`, the Yandex base URL, `gpt://` model URIs,
model names, SDK construction and primary/fallback ordering.

## Technical contract

The gateway owns only model transport and provider selection. Callers continue
to own authorization, tenant scope, prompt construction, response validation,
business fallback behavior and every database write.

The first contract supports the capabilities already used by the application:

- text input and text output;
- structured multi-part input containing text, images or uploaded-file IDs;
- explicit temperature and maximum-output-token bounds;
- an ordered logical model policy supplied by a closed source-code registry;
- a detached result containing output text plus non-secret provider/model and
  duration metadata;
- fixed typed failures for unavailable configuration, provider failure, empty
  output and deadline/cancellation.

The public gateway contract must never expose API keys, folder IDs, raw SDK
objects, request headers, provider exception text or full prompt content in
logs or errors.

## Implementation slices

### A14.1: Pure contract and inventory gate

- Add immutable request/result/error types and a closed capability/model-policy
  registry.
- Add a static inventory test that lists every direct provider access point and
  fails if an unregistered new import, URL or SDK call appears.
- Do not import the OpenAI SDK, read environment variables, make network calls
  or register runtime code.

### A14.2: Existing Yandex adapter

- Implement the current OpenAI-compatible Yandex transport behind the gateway.
- Preserve current model URIs, timeouts, token limits and fallback order.
- Inject a fake client in tests; no external model call is made by tests.
- Keep the legacy Foundation Models HTTP call unchanged until its own slice.

### A14.3: First low-risk caller

- Move `_generate_estimate_chat_answer` to the gateway without changing its
  prompt, output, error mapping or route behavior.
- Prove old and new calls produce the same SDK request and caller-visible
  result using a fake provider.
- Keep a small rollback path limited to that caller.

### A14.4: Remaining callers

- Migrate one domain per commit, preserving each domain's current authorization,
  validation, fallback and write behavior.
- Remove direct provider access only after the domain's focused tests pass.
- Migrate the legacy direct HTTP caller in a dedicated final compatibility
  slice.

### A14.5: Measurement before local-model evaluation

- Record bounded per-capability success, invalid-response, latency and token/
  cost metrics without prompts or business payloads.
- Build a redacted, human-approved evaluation set and acceptance thresholds.
- Evaluate a local model offline. Do not route production traffic to it until a
  separate rollout decision and canary plan are approved.

## Commands

```bash
PYTHONPYCACHEPREFIX=/tmp/stroyka-a14-pycache \
python3 -m unittest backend.features.model_gateway.test_contract

PYTHONPYCACHEPREFIX=/tmp/stroyka-a14-pycache \
python3 -m unittest discover -s backend -p 'test_*.py'

PYTHONPYCACHEPREFIX=/tmp/stroyka-a14-pycache \
python3 -m py_compile backend/main.py backend/features/model_gateway/*.py

git diff --check
```

Frontend tests and `npm run build` are required only for a slice that changes
frontend code or the frontend-facing API contract.

## Project structure

```text
backend/features/model_gateway/
  contract.py          immutable provider-neutral values and failures
  policies.py          closed logical capability/model policies
  inventory.py         static direct-access inventory gate
  yandex_adapter.py    existing cloud transport, added only in A14.2
  test_*.py            small no-network tests beside each slice
docs/model-provider-gateway.md
```

## Code style

The boundary uses explicit immutable values and dependency injection rather
than a generic plugin framework:

```python
request = ModelRequest(
    capability="estimate_chat",
    instructions=instructions,
    input_text=prompt,
    temperature=0.1,
    max_output_tokens=4000,
)
result = gateway.generate(request)
```

Capabilities and policies are fixed source-code values. Arbitrary model IDs,
provider URLs and credentials are never accepted from HTTP or database input.

## Testing strategy

- Small contract tests cover immutability, bounds, closed fields and secret-safe
  failures.
- Static inventory tests fail when direct provider access grows outside the
  reviewed baseline.
- Adapter tests use a fake SDK client and compare exact request arguments,
  fallback order, empty output and redacted failures.
- Every migrated caller gets a behavior-parity regression test before its old
  direct call is removed.
- Full backend discovery and compilation run after every slice.

## Boundaries

Always:

- keep the existing cloud provider first during migration;
- preserve prompts, response validation and caller-visible errors per slice;
- keep secrets and prompt/business payloads out of logs and public failures;
- use explicit deadlines and bounded input/output values;
- commit and verify one caller/domain at a time.

Ask first:

- connect the gateway to production runtime;
- change a model, fallback order, prompt or error mapping;
- add a dependency, provider, local-model process or network destination;
- add metrics storage, schema, feature flags, deployment or canary traffic.

Never:

- select a provider or model from untrusted request/database content;
- silently send production data to a local or new external model;
- log credentials, full prompts, uploaded documents or raw provider errors;
- let the gateway authorize users, mutate business rows or parse domain JSON;
- keep two active implementations after a caller has passed parity tests.

## Success criteria

- All model calls eventually cross one provider-neutral gateway.
- No business module constructs a provider client, URL or `gpt://` model URI.
- Current production behavior remains unchanged throughout migration.
- A static gate prevents new direct provider calls.
- Per-capability measurements exist before any local-model decision.
- Production provider changes require a separate explicit approval and canary.

## Open questions

- Exact quality thresholds and evaluation fixtures for each capability are
  deferred until the gateway can measure the existing cloud baseline.
- Local runtime, hardware and model choice are intentionally undecided until
  the baseline proves the required quality, latency and capacity.
