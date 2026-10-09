# model-adapters

Public catalog of model adapters shared by BlazeAI and FluxAI (FluxHub relay): per provider and
model, the wire protocol, capabilities, and protocol options.

Raw URL (default for both applications):
`https://raw.githubusercontent.com/mariusg0000/model-adapters/main/model_adapters.json`

## Schema (`schema_version` 1)

```
{ "schema_version": 1, "revision": <int>, "providers": { "<provider>": {
    "auth_type": "api_key" | "oauth",
    "default_protocol": "openai-chat" | "openai-responses" | "openai-responses-api" | "anthropic-messages",
    "openai_chat": {"include_stream_usage": bool, "include_reasoning_content": bool},   // optional
    "responses":   {"lite": bool},                                                     // optional
    "anthropic":   {"max_tokens": <positive int>},                                     // optional
    "models": { "<exact model id>": {
        "tools": bool, "reasoning": bool,
        "reasoning_levels": ["low", ...],        // optional, needs reasoning=true
        "protocol": "<one of the four>",         // optional override
        "openai_chat" / "responses" / "anthropic": { ... }   // optional overrides
    } } } } }
```

- `anthropic-messages` needs `anthropic.max_tokens` (model or provider) and `auth_type: api_key`.
- `openai-responses` is the Codex OAuth dialect; `openai-responses-api` is the standard API-key one.
- No endpoint or credential field exists on purpose: the catalog can never redirect requests.
- Increase `revision` on every content change. A breaking schema change bumps `schema_version`.

## Consumers

- BlazeAI: all fields.
- FluxAI hub: `default_protocol`, model `protocol`, `anthropic.max_tokens`, `tools`, `reasoning`
  (prefill of the console source row). Maps `openai-chat`→`chat`, `openai-responses-api`→`responses`,
  `anthropic-messages`→`anthropic`; OAuth/Codex entries are skipped. Unknown fields are ignored.

## Publishing

```
python3 scripts/validate.py model_adapters.json   # must print "ok"
git commit -am "..." && git push
```
