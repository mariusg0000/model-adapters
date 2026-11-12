#!/usr/bin/env python3
"""Generate model_adapters.json from models.dev plus overrides.json.

WHAT: Rebuilds the catalog providers from models.dev model facts and the hand-written overrides.
      Leaves the file untouched when the providers are unchanged; otherwise writes it with
      revision + 1. Exit 0 on success or no change; exit 1 with the errors on any failure, and
      the file is then unchanged.
HOW:  Stdlib only. Fetches https://models.dev/api.json unless --models-dev names a local copy.
      The new document is validated with scripts/validate.py before it is written.
"""
import argparse
import json
import os
import sys
import urllib.request

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(SCRIPTS_DIR)
sys.path.insert(0, SCRIPTS_DIR)
from validate import validate  # noqa: E402

MODELS_DEV_URL = "https://models.dev/api.json"
SDK_PROTOCOLS = {
    "@ai-sdk/anthropic": "anthropic-messages",
    "@ai-sdk/openai": "openai-responses-api",
    "@ai-sdk/google": "google-generate-content",
}


class GenerationError(Exception):
    pass


def effort_levels(mdev_model):
    # WHAT: levels come only from the first "effort" option; other option kinds give none.
    for option in mdev_model.get("reasoning_options") or []:
        if option.get("type") == "effort":
            return list(option.get("values") or [])
    return []


def sdk_protocol(mdev_model, mdev_provider):
    npm = (mdev_model.get("provider") or {}).get("npm") or mdev_provider.get("npm")
    return SDK_PROTOCOLS.get(npm, "openai-chat")


def generated_model(mdev_model, mdev_provider, default_protocol):
    entry = {
        "tools": mdev_model.get("tool_call") is True,
        "reasoning": mdev_model.get("reasoning") is True,
    }
    if entry["reasoning"]:
        levels = effort_levels(mdev_model)
        if levels:
            entry["reasoning_levels"] = levels
    protocol = sdk_protocol(mdev_model, mdev_provider)
    if protocol != default_protocol:
        entry["protocol"] = protocol
    if protocol == "anthropic-messages":
        output = (mdev_model.get("limit") or {}).get("output")
        if output is not None:
            entry["anthropic"] = {"max_tokens": output}
    return entry


def generated_models(name, spec, default_protocol, models_dev):
    mdev_provider = models_dev.get(spec["provider"])
    if mdev_provider is None:
        raise GenerationError(f"providers.{name}: unknown models.dev provider {spec['provider']!r}")
    mdev_models = mdev_provider.get("models") or {}
    ids = spec["only"] if "only" in spec else list(mdev_models)
    models = {}
    for mid in ids:
        if mid not in mdev_models:
            print(f"note: {name}: {mid} is not in models.dev, skipped", file=sys.stderr)
            continue
        models[mid] = generated_model(mdev_models[mid], mdev_provider, default_protocol)
    return models


def build_provider(name, block, models_dev):
    # WHAT: override models are merged field by field over the generated ones; an override model
    # without a generated entry is kept as written.
    provider = {k: v for k, v in block.items() if k not in ("models_dev", "models")}
    models = {}
    if "models_dev" in block:
        models = generated_models(name, block["models_dev"], block.get("default_protocol"), models_dev)
    for mid, override in block.get("models", {}).items():
        models[mid] = {**models[mid], **override} if mid in models else override
    provider["models"] = dict(sorted(models.items()))
    return provider


def build_providers(overrides, models_dev):
    # WHAT: providers keep the order of overrides.json.
    return {name: build_provider(name, block, models_dev) for name, block in overrides["providers"].items()}


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def fetch_models_dev():
    request = urllib.request.Request(MODELS_DEV_URL, headers={"User-Agent": "model-adapters-generator"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))


def main(argv=None):
    parser = argparse.ArgumentParser(description="Generate model_adapters.json from models.dev.")
    parser.add_argument("--models-dev", metavar="FILE", help="local models.dev api.json instead of fetching it")
    args = parser.parse_args(argv)
    catalog_path = os.path.join(ROOT, "model_adapters.json")
    try:
        overrides = load_json(os.path.join(ROOT, "overrides.json"))
        current = load_json(catalog_path)
        models_dev = load_json(args.models_dev) if args.models_dev else fetch_models_dev()
        providers = build_providers(overrides, models_dev)
    except (OSError, ValueError, GenerationError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    if providers == current["providers"]:
        print(f"unchanged (revision {current['revision']})")
        return 0
    document = {"schema_version": 1, "revision": current["revision"] + 1, "providers": providers}
    errors = validate(document)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    with open(catalog_path, "w", encoding="utf-8") as f:
        f.write(json.dumps(document, indent=2) + "\n")
    print(f"updated to revision {document['revision']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
