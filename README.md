# model-adapters

Public catalog of model adapters shared by BlazeAI and FluxAI (FluxHub relay): per provider and
model, the wire protocol, capabilities, and protocol options.

Raw URL (default for both applications):
`https://raw.githubusercontent.com/mariusg0000/model-adapters/main/model_adapters.json`

## Schema (`schema_version` 1)

```
{ "schema_version": 1, "revision": <int>, "providers": { "<provider>": {
    "auth_type": "api_key" | "oauth",
    "default_protocol": "openai-chat" | "openai-responses" | "openai-responses-api" | "anthropic-messages"
                        | "google-generate-content",
    "openai_chat": {"include_stream_usage": bool, "include_reasoning_content": bool},   // optional
    "responses":   {"lite": bool},                                                     // optional
    "anthropic":   {"max_tokens": <positive int>},                                     // optional
    "models": { "<exact model id>": {
        "tools": bool, "reasoning": bool,
        "reasoning_levels": ["low", ...],        // optional, needs reasoning=true
        "protocol": "<one of the five>",         // optional override
        "openai_chat" / "responses" / "anthropic": { ... }   // optional overrides
    } } } } }
```

- `anthropic-messages` needs `anthropic.max_tokens` (model or provider) and `auth_type: api_key`.
- `openai-responses` is the Codex OAuth dialect; `openai-responses-api` is the standard API-key one.
- `google-generate-content` is the native Gemini `generateContent` API (opencode serves it at a
  different endpoint than its OpenAI-compatible gateway; the consumer configures that endpoint).
- No endpoint or credential field exists on purpose: the catalog can never redirect requests.
- `revision` increases on every content change (the generator does it). A breaking schema change bumps
  `schema_version`.

## Consumers

Model data is added or changed only here; consumers keep no model facts of their own.

- BlazeAI: all fields (does not support `google-generate-content` yet).
- FluxAI hub: `default_protocol`, model `protocol`, `anthropic.max_tokens`, `tools`, `reasoning`,
  `reasoning_levels`, `responses.lite`; a hub source names only a catalog model and a level, the
  relay resolves the rest from here. Maps `openai-chat`→`chat`, `openai-responses-api`→`responses`,
  `anthropic-messages`→`anthropic`, `openai-responses`→`responses` (Codex OAuth),
  `google-generate-content`→`google`. Unknown fields are ignored; a model with an unknown protocol
  is skipped.

## Generation

`model_adapters.json` is generated; never edit it by hand.

- `scripts/generate.py` takes the models of each provider from [models.dev](https://models.dev)
  (`tool_call`, `reasoning`, the `effort` reasoning levels, the protocol from the model's SDK package,
  `max_tokens` from `limit.output`), applies `overrides.json`, validates, and raises `revision` only
  when the content changes. A model models.dev drops leaves the catalog.
- `overrides.json` lists the providers and their order. A provider with a `models_dev` block takes all
  models of that models.dev provider, or only the ids in `only`; one without it (Codex OAuth) is
  written by hand. Provider fields are copied as written; an override model is merged field by field
  over the generated one (override wins) or added as written when models.dev lacks it.
- A GitHub Action (`.github/workflows/generate.yml`) runs the tests and the generator daily, on manual
  dispatch, and on every push to `main`, and commits the catalog when it changed.

## Changing models

Corrections, live-tested levels, consumer options, and models models.dev lacks go in `overrides.json`:

```
git pull                                      # the Action commits the catalog too
# edit overrides.json
python3 scripts/generate.py                   # regenerates and validates model_adapters.json
git commit -am "..." && git push
```
