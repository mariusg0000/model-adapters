#!/usr/bin/env python3
"""Validate model_adapters.json against the shared schema (schema_version 1).

WHAT: Strict check run locally before every push; exit 0 when valid, 1 with one error per line.
HOW:  Stdlib only. Unknown fields are rejected here (the publisher is strict); consumers ignore
      fields they do not use.
"""
import json
import re
import sys

PROTOCOLS = {"openai-chat", "openai-responses", "openai-responses-api", "anthropic-messages"}
AUTH = {"api_key", "oauth"}
LEVEL = re.compile(r"^[a-z0-9_-]+$")
MAX_LEVELS = 16

PROVIDER_FIELDS = {"auth_type", "default_protocol", "openai_chat", "responses", "anthropic", "models"}
MODEL_FIELDS = {"tools", "reasoning", "reasoning_levels", "protocol", "openai_chat", "responses", "anthropic"}
CHAT_FIELDS = {"include_stream_usage", "include_reasoning_content"}


def is_int(v):
    return isinstance(v, int) and not isinstance(v, bool)


def check_block(where, block, allowed, errors, kind):
    if not isinstance(block, dict):
        errors.append(f"{where}: must be an object")
        return
    for k, v in block.items():
        if k not in allowed:
            errors.append(f"{where}.{k}: unknown field")
        elif kind == "bool" and not isinstance(v, bool):
            errors.append(f"{where}.{k}: must be boolean")
        elif kind == "int" and not (is_int(v) and v > 0):
            errors.append(f"{where}.{k}: must be a positive integer")


def check_variants(where, entry, errors):
    if "openai_chat" in entry:
        check_block(f"{where}.openai_chat", entry["openai_chat"], CHAT_FIELDS, errors, "bool")
    if "responses" in entry:
        check_block(f"{where}.responses", entry["responses"], {"lite"}, errors, "bool")
    if "anthropic" in entry:
        check_block(f"{where}.anthropic", entry["anthropic"], {"max_tokens"}, errors, "int")


def check_levels(where, model, errors):
    levels = model["reasoning_levels"]
    if model.get("reasoning") is not True:
        errors.append(f"{where}.reasoning_levels: requires reasoning=true")
    if not isinstance(levels, list) or not levels or len(levels) > MAX_LEVELS:
        errors.append(f"{where}.reasoning_levels: must be a non-empty list of at most {MAX_LEVELS}")
        return
    if len(set(map(str, levels))) != len(levels):
        errors.append(f"{where}.reasoning_levels: duplicate entry")
    for lv in levels:
        if not isinstance(lv, str) or not LEVEL.match(lv):
            errors.append(f"{where}.reasoning_levels: invalid entry {lv!r}")


def check_model(where, name, model, provider, errors):
    if "*" in name or not name:
        errors.append(f"{where}: invalid model id (no wildcards)")
    if not isinstance(model, dict):
        errors.append(f"{where}: must be an object")
        return
    for k in model:
        if k not in MODEL_FIELDS:
            errors.append(f"{where}.{k}: unknown field")
    for k in ("tools", "reasoning"):
        if not isinstance(model.get(k), bool):
            errors.append(f"{where}.{k}: required boolean")
    if "reasoning_levels" in model:
        check_levels(where, model, errors)
    if "protocol" in model and model["protocol"] not in PROTOCOLS:
        errors.append(f"{where}.protocol: must be one of {sorted(PROTOCOLS)}")
    check_variants(where, model, errors)
    protocol = model.get("protocol", provider.get("default_protocol"))
    effective = model.get("anthropic", provider.get("anthropic"))
    if protocol == "anthropic-messages":
        if not isinstance(effective, dict) or "max_tokens" not in effective:
            errors.append(f"{where}: anthropic-messages requires anthropic.max_tokens")
        if provider.get("auth_type") != "api_key":
            errors.append(f"{where}: anthropic-messages requires auth_type api_key")
    elif "anthropic" in model:
        errors.append(f"{where}.anthropic: only valid for anthropic-messages")


def validate(data):
    errors = []
    if not isinstance(data, dict):
        return ["root: must be an object"]
    for k in data:
        if k not in {"schema_version", "revision", "providers"}:
            errors.append(f"root.{k}: unknown field")
    if data.get("schema_version") != 1 or not is_int(data.get("schema_version")):
        errors.append("schema_version: must be 1")
    if not (is_int(data.get("revision")) and data["revision"] > 0):
        errors.append("revision: must be a positive integer")
    providers = data.get("providers")
    if not isinstance(providers, dict) or not providers:
        errors.append("providers: must be a non-empty object")
        return errors
    for pname, provider in providers.items():
        where = f"providers.{pname}"
        if not isinstance(provider, dict):
            errors.append(f"{where}: must be an object")
            continue
        for k in provider:
            if k not in PROVIDER_FIELDS:
                errors.append(f"{where}.{k}: unknown field")
        if provider.get("auth_type") not in AUTH:
            errors.append(f"{where}.auth_type: must be one of {sorted(AUTH)}")
        if provider.get("default_protocol") not in PROTOCOLS:
            errors.append(f"{where}.default_protocol: must be one of {sorted(PROTOCOLS)}")
        check_variants(where, provider, errors)
        models = provider.get("models")
        if not isinstance(models, dict) or not models:
            errors.append(f"{where}.models: must be a non-empty object")
            continue
        for mname, model in models.items():
            check_model(f"{where}.models.{mname}", mname, model, provider, errors)
    return errors


def main():
    if len(sys.argv) != 2:
        print("usage: validate.py model_adapters.json", file=sys.stderr)
        return 2
    try:
        with open(sys.argv[1], encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError) as e:
        print(f"cannot read {sys.argv[1]}: {e}", file=sys.stderr)
        return 1
    errors = validate(data)
    for e in errors:
        print(e)
    if not errors:
        print("ok")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
