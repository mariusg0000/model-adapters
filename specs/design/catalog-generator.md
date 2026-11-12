# Catalog generator

WHAT: `model_adapters.json` is generated from models.dev plus a small hand-written `overrides.json`,
and a daily GitHub Action keeps it current.
HOW: `scripts/generate.py` maps models.dev model facts to the unchanged schema (`schema_version` 1),
applies the overrides, validates, and raises `revision` only when the content changes.

## Scope

In scope: `scripts/generate.py`, `overrides.json`, generator tests, the GitHub Action, README and
project-context updates, and the first regenerated catalog.

Out of scope: schema changes (`schema_version` stays 1); consumer changes (FluxAI hub, BlazeAI read the
catalog as before); providers models.dev does not have, beyond keeping them by hand.

**Approval:** implementation approved by the user ("da", 2026-11-12), with OpenRouter limited to a
chosen list and `Versioning: none`.

**Rationale:** the hand-kept catalog fell behind models.dev (12 new models, missing reasoning levels, 5
retired models still listed), while for the models present in both the facts were identical. Only a
small layer (live-tested corrections, providers absent from models.dev, consumer options) needs a person.

## Requirements

### [X] Generation from models.dev

**Description:**
- Inputs: `https://models.dev/api.json` (or a local copy given on the command line), `overrides.json`,
  and the current `model_adapters.json`.
- `overrides.json` lists the catalog providers and their order. A provider with a `models_dev` block takes
  its models from that models.dev provider: all of them, or only the ids listed in `only`. A provider
  without the block is fully hand-written (Codex OAuth, which models.dev does not have).
- Per models.dev model: `tools` from `tool_call`; `reasoning` from `reasoning`; `reasoning_levels` from the
  values of its `effort` reasoning option, only when `reasoning` is true (other option kinds give no
  levels); the protocol from the model's SDK package (`provider.npm` of the model, else of the models.dev
  provider): `@ai-sdk/anthropic` → `anthropic-messages`, `@ai-sdk/openai` → `openai-responses-api`,
  `@ai-sdk/google` → `google-generate-content`, any other → `openai-chat`. `protocol` is written only
  when it differs from the provider's `default_protocol`; `anthropic.max_tokens` comes from
  `limit.output` for `anthropic-messages` models.
- Models models.dev marks deprecated are kept (still served); a model leaves the catalog when models.dev
  drops it. An `only` id missing from models.dev is skipped with a note, so a retired model never breaks
  the daily run.
- Overrides: provider fields other than `models_dev` and `models` are copied as written; each override
  model is merged field by field over the generated entry (the override wins); an override model absent
  from models.dev is added as written.
- Output: models sorted by id per provider, 2-space JSON. When the generated providers equal the current
  ones the file is left untouched; otherwise `revision` is the current one plus 1. The result must pass
  `scripts/validate.py` before it is written; any error (fetch, validation, unknown models.dev provider)
  exits non-zero and leaves the file unchanged.

**Acceptance:** generated from the current models.dev, the catalog keeps every model the FluxAI hub
uses with the same facts (including the live-tested `max` level of `gemini-4-argon` and the hand-kept
Codex models and `~typesafe/jev-latest`), validates `ok`, and a second run with the same input changes
nothing.

**Implemented:** [catalog-generator.md](../implemented/catalog-generator.md).

### [X] Daily GitHub Action

**Description:** a workflow runs on a daily schedule, on manual dispatch, and on push to `main`: it runs
the generator tests, generates, validates, and commits and pushes `model_adapters.json` only when it
changed.

**Acceptance:** a run on GitHub succeeds and commits only a changed catalog.

**Rationale:** keeps the catalog current without manual work, regenerates after a pushed overrides change,
and is the CI the project lacked.

**Implemented:** [catalog-generator.md](../implemented/catalog-generator.md).

### [X] Editing procedure

**Description:** `model_adapters.json` is never edited by hand: a correction or a hand-kept model goes in
`overrides.json`, then `scripts/generate.py` runs before commit and push. README and project context state
it.

**Implemented:** [catalog-generator.md](../implemented/catalog-generator.md).
