# Catalog generator

WHAT: `model_adapters.json` is generated from models.dev plus the hand-written `overrides.json`, and a
GitHub Action regenerates and commits it daily, on manual dispatch, and on push to `main`.
HOW: `scripts/generate.py` (stdlib) maps models.dev model facts to the unchanged schema
(`schema_version` 1), applies the overrides, validates with `scripts/validate.py`, and raises `revision`
only when the providers change.

## Scope

Generation, the overrides layer, the daily workflow, and the editing procedure. The schema and the
consumers (FluxAI hub, BlazeAI) are unchanged; they read the catalog as before.

## Behavior and Contracts

- Inputs: `https://models.dev/api.json` (or `--models-dev FILE`), `overrides.json`, and the current
  `model_adapters.json`.
- `overrides.json` lists the catalog providers in output order. A provider with
  `models_dev: {provider, only?}` takes all models of that models.dev provider, or only the `only` ids;
  a provider without it is written entirely by hand (Codex OAuth).
- Per models.dev model: `tools` ← `tool_call`; `reasoning` ← `reasoning`; `reasoning_levels` ← the
  values of the first `effort` reasoning option, only when `reasoning` is true; protocol ← the model's
  `provider.npm`, else the models.dev provider's `npm`: `@ai-sdk/anthropic` → `anthropic-messages`,
  `@ai-sdk/openai` → `openai-responses-api`, `@ai-sdk/google` → `google-generate-content`, any other →
  `openai-chat`. `protocol` is written only when it differs from `default_protocol`;
  `anthropic.max_tokens` ← `limit.output` for `anthropic-messages` models.
- Deprecated models stay (still served); a model models.dev drops leaves the catalog. An `only` id
  missing from models.dev is skipped with a note, so a retired model never breaks a run.
- Overrides: provider fields other than `models_dev` and `models` are copied as written; an override
  model is merged field by field over the generated entry (override wins) or added as written when
  models.dev lacks it.
- Output: models sorted by id per provider, 2-space JSON. Equal providers leave the file untouched
  (exit 0, "unchanged"); otherwise `revision` is the current one plus 1. Any fetch, validation, or
  unknown-provider error exits 1 and leaves the file unchanged.
- Workflow `.github/workflows/generate.yml`: cron `17 3 * * *`, `workflow_dispatch`, push to `main`;
  runs the generator tests, generates, validates, and commits only `model_adapters.json` as
  `github-actions[bot]` ("Update catalog from models.dev (revision N)") when it changed; one run at a
  time (concurrency group `generate-catalog`).
- Editing procedure: `model_adapters.json` is never edited by hand. A correction, a live-tested level,
  a consumer option, or a model models.dev lacks goes in `overrides.json`; then `git pull` (the Action
  commits too), `scripts/generate.py`, commit, push.

## Integration and Constraints

- models.dev is untrusted input: the result must pass the strict validator before it is written, and
  the schema has no endpoint or credential fields.
- OpenRouter is limited to the `only` list, so the large models.dev OpenRouter catalog does not enter.
- Current hand-kept data: all Codex OAuth models; opencode-go provider options and the live-tested
  `max` level of `gemini-4-argon`; OpenRouter `~typesafe/jev-latest`.
- A model retired by models.dev disappears from both consumers after the next run; a consumer source
  that still names it no longer resolves.

## References

- `scripts/generate.py`, `scripts/test_generate.py`, `overrides.json`, `.github/workflows/generate.yml`,
  `scripts/validate.py`, `README.md`.
- Design: [catalog-generator.md](../design/catalog-generator.md).
