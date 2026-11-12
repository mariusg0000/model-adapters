#!/usr/bin/env python3
"""Unit and CLI tests for scripts/generate.py.

WHAT: Covers the models.dev field mapping, overrides, provider order, and the revision and
      failure behavior of the CLI. No network: models.dev data is inline or a temporary file.
HOW:  Run with `python3 -m unittest discover -s scripts -p 'test_*.py'`. CLI tests copy the
      generator and validator into a temporary repository root.
"""
import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPTS_DIR)
import generate  # noqa: E402
import validate  # noqa: E402


def mdev_model(**fields):
    return {"tool_call": True, "reasoning": True, **fields}


def one_model_providers(model, provider_npm=None, default_protocol="openai-chat"):
    mdev_provider = {"models": {"m": model}}
    if provider_npm is not None:
        mdev_provider["npm"] = provider_npm
    overrides = {"providers": {"p": {
        "models_dev": {"provider": "src"}, "auth_type": "api_key", "default_protocol": default_protocol}}}
    return generate.build_providers(overrides, {"src": mdev_provider})["p"]["models"]["m"]


class FieldMapping(unittest.TestCase):
    def test_tools_and_reasoning_copied(self):
        entry = one_model_providers(mdev_model(reasoning_options=[{"type": "effort", "values": ["low"]}]))
        self.assertIs(entry["tools"], True)
        self.assertIs(entry["reasoning"], True)
        self.assertEqual(entry["reasoning_levels"], ["low"])

    def test_missing_or_false_tool_call_gives_false_tools(self):
        entry = one_model_providers({"reasoning": False})
        self.assertIs(entry["tools"], False)
        self.assertIs(entry["reasoning"], False)

    def test_effort_values_become_levels_in_order(self):
        entry = one_model_providers(mdev_model(reasoning_options=[
            {"type": "toggle"}, {"type": "effort", "values": ["low", "high", "max"]}]))
        self.assertEqual(entry["reasoning_levels"], ["low", "high", "max"])

    def test_toggle_only_gives_no_levels(self):
        entry = one_model_providers(mdev_model(reasoning_options=[{"type": "toggle"}]))
        self.assertNotIn("reasoning_levels", entry)

    def test_budget_tokens_only_gives_no_levels(self):
        entry = one_model_providers(mdev_model(reasoning_options=[{"type": "budget_tokens"}]))
        self.assertNotIn("reasoning_levels", entry)

    def test_reasoning_false_gives_no_levels(self):
        entry = one_model_providers(mdev_model(
            reasoning=False, reasoning_options=[{"type": "effort", "values": ["low"]}]))
        self.assertNotIn("reasoning_levels", entry)
        self.assertIs(entry["reasoning"], False)


class Protocol(unittest.TestCase):
    def test_model_npm_beats_provider_npm(self):
        entry = one_model_providers(
            mdev_model(provider={"npm": "@ai-sdk/anthropic"}, limit={"output": 4096}), provider_npm="@ai-sdk/openai")
        self.assertEqual(entry["protocol"], "anthropic-messages")

    def test_provider_npm_used_without_model_npm(self):
        entry = one_model_providers(mdev_model(), provider_npm="@ai-sdk/openai")
        self.assertEqual(entry["protocol"], "openai-responses-api")

    def test_google_npm_maps_to_generate_content(self):
        entry = one_model_providers(mdev_model(provider={"npm": "@ai-sdk/google"}))
        self.assertEqual(entry["protocol"], "google-generate-content")

    def test_unknown_npm_maps_to_openai_chat(self):
        entry = one_model_providers(mdev_model(), provider_npm="@ai-sdk/unknown", default_protocol="openai-responses-api")
        self.assertEqual(entry["protocol"], "openai-chat")

    def test_protocol_omitted_when_equal_to_default(self):
        entry = one_model_providers(mdev_model(), provider_npm="@ai-sdk/openai-compatible")
        self.assertNotIn("protocol", entry)

    def test_anthropic_messages_gets_max_tokens_from_limit_output(self):
        entry = one_model_providers(mdev_model(provider={"npm": "@ai-sdk/anthropic"}, limit={"output": 4096}))
        self.assertEqual(entry["protocol"], "anthropic-messages")
        self.assertEqual(entry["anthropic"], {"max_tokens": 4096})


class OnlyFilter(unittest.TestCase):
    def test_only_keeps_listed_ids_and_skips_missing_with_note(self):
        overrides = {"providers": {"p": {
            "models_dev": {"provider": "src", "only": ["a", "gone"]},
            "auth_type": "api_key", "default_protocol": "openai-chat"}}}
        models_dev = {"src": {"models": {"a": mdev_model(), "b": mdev_model()}}}
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            providers = generate.build_providers(overrides, models_dev)
        self.assertEqual(list(providers["p"]["models"]), ["a"])
        self.assertIn("gone", stderr.getvalue())

    def test_unknown_models_dev_provider_is_an_error(self):
        overrides = {"providers": {"p": {"models_dev": {"provider": "nope"}, "auth_type": "api_key",
                                         "default_protocol": "openai-chat"}}}
        with self.assertRaises(generate.GenerationError):
            generate.build_providers(overrides, {"src": {"models": {}}})


class ProviderCopy(unittest.TestCase):
    def test_provider_without_models_dev_is_copied_exactly(self):
        block = {"auth_type": "oauth", "default_protocol": "openai-responses", "responses": {"lite": False},
                 "models": {"x": {"tools": True, "reasoning": True, "reasoning_levels": ["low"]}}}
        providers = generate.build_providers({"providers": {"chatgpt": block}}, {})
        self.assertEqual(providers, {"chatgpt": block})

    def test_provider_fields_copied_and_models_dev_never_emitted(self):
        overrides = {"providers": {"p": {
            "models_dev": {"provider": "src"}, "auth_type": "api_key", "default_protocol": "openai-chat",
            "openai_chat": {"include_stream_usage": True, "include_reasoning_content": True}}}}
        providers = generate.build_providers(overrides, {"src": {"models": {"a": mdev_model()}}})
        self.assertEqual(providers["p"]["openai_chat"],
                         {"include_stream_usage": True, "include_reasoning_content": True})
        self.assertNotIn("models_dev", providers["p"])


class OverrideMerge(unittest.TestCase):
    def test_override_field_replaces_generated_and_other_fields_kept(self):
        overrides = {"providers": {"p": {
            "models_dev": {"provider": "src"}, "auth_type": "api_key", "default_protocol": "openai-chat",
            "models": {"a": {"reasoning_levels": ["low", "max"]}}}}}
        models_dev = {"src": {"models": {"a": mdev_model(
            reasoning_options=[{"type": "effort", "values": ["low", "high"]}])}}}
        entry = generate.build_providers(overrides, models_dev)["p"]["models"]["a"]
        self.assertEqual(entry, {"tools": True, "reasoning": True, "reasoning_levels": ["low", "max"]})

    def test_override_only_model_added_as_written(self):
        overrides = {"providers": {"p": {
            "models_dev": {"provider": "src"}, "auth_type": "api_key", "default_protocol": "openai-chat",
            "models": {"hand-kept": {"tools": True, "reasoning": True}}}}}
        models = generate.build_providers(overrides, {"src": {"models": {}}})["p"]["models"]
        self.assertEqual(models, {"hand-kept": {"tools": True, "reasoning": True}})


class OrderAndDeprecated(unittest.TestCase):
    def test_deprecated_kept_models_sorted_and_provider_order_kept(self):
        overrides = {"providers": {
            "zeta": {"models_dev": {"provider": "src"}, "auth_type": "api_key", "default_protocol": "openai-chat"},
            "alpha": {"auth_type": "api_key", "default_protocol": "openai-chat",
                      "models": {"x": {"tools": False, "reasoning": False}}}}}
        models_dev = {"src": {"models": {
            "c": mdev_model(status="deprecated"), "a": mdev_model(), "b": mdev_model()}}}
        providers = generate.build_providers(overrides, models_dev)
        self.assertEqual(list(providers), ["zeta", "alpha"])
        self.assertEqual(list(providers["zeta"]["models"]), ["a", "b", "c"])


FIXTURE_OVERRIDES = {"providers": {
    "src-provider": {
        "models_dev": {"provider": "src"}, "auth_type": "api_key", "default_protocol": "openai-chat"},
    "hand-provider": {
        "auth_type": "oauth", "default_protocol": "openai-responses", "responses": {"lite": False},
        "models": {"hand-model": {"tools": True, "reasoning": True, "reasoning_levels": ["low"]}}},
}}


def fixture_models_dev(tool_call=True):
    return {"src": {"npm": "@ai-sdk/openai-compatible", "models": {
        "chat": mdev_model(tool_call=tool_call, reasoning_options=[{"type": "effort", "values": ["low", "high"]}])}}}


class Cli(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.root = os.path.join(self.tmp, "repo")
        os.makedirs(os.path.join(self.root, "scripts"))
        for name in ("generate.py", "validate.py"):
            shutil.copy(os.path.join(SCRIPTS_DIR, name), os.path.join(self.root, "scripts", name))
        self.write_json("overrides.json", FIXTURE_OVERRIDES)
        self.write_json("model_adapters.json", {"schema_version": 1, "revision": 7, "providers": {}})
        self.models_dev = os.path.join(self.tmp, "models-dev.json")
        self.write_json_path(self.models_dev, fixture_models_dev())

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def write_json(self, name, data):
        self.write_json_path(os.path.join(self.root, name), data)

    def write_json_path(self, path, data):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f)

    def run_generator(self, models_dev=None):
        command = [sys.executable, os.path.join(self.root, "scripts", "generate.py")]
        if models_dev is not None:
            command += ["--models-dev", models_dev]
        return subprocess.run(command, capture_output=True, text=True)

    def catalog_path(self):
        return os.path.join(self.root, "model_adapters.json")

    def read_bytes(self):
        with open(self.catalog_path(), "rb") as f:
            return f.read()

    def test_same_content_leaves_file_and_revision_unchanged(self):
        first = self.run_generator(self.models_dev)
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertIn("updated to revision 8", first.stdout)
        before = self.read_bytes()
        second = self.run_generator(self.models_dev)
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertIn("unchanged (revision 8)", second.stdout)
        self.assertEqual(self.read_bytes(), before)

    def test_changed_content_raises_revision_and_file_is_valid(self):
        self.assertEqual(self.run_generator(self.models_dev).returncode, 0)
        self.write_json_path(self.models_dev, fixture_models_dev(tool_call=False))
        result = self.run_generator(self.models_dev)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("updated to revision 9", result.stdout)
        with open(self.catalog_path(), encoding="utf-8") as f:
            document = json.load(f)
        self.assertEqual(document["revision"], 9)
        self.assertEqual(validate.validate(document), [])
        self.assertIs(document["providers"]["src-provider"]["models"]["chat"]["tools"], False)

    def test_validation_failure_exits_1_and_leaves_file_unchanged(self):
        self.write_json("overrides.json", {"providers": {
            "src-provider": {"models_dev": {"provider": "src"}, "auth_type": "api_key",
                             "default_protocol": "openai-chat",
                             "models": {"chat": {"reasoning_levels": ["Not Valid"]}}}}})
        before = self.read_bytes()
        result = self.run_generator(self.models_dev)
        self.assertEqual(result.returncode, 1)
        self.assertIn("reasoning_levels", result.stderr)
        self.assertEqual(self.read_bytes(), before)

    def test_unknown_models_dev_provider_exits_1_and_leaves_file_unchanged(self):
        self.write_json("overrides.json", {"providers": {
            "x": {"models_dev": {"provider": "no-such-provider"}, "auth_type": "api_key",
                  "default_protocol": "openai-chat"}}})
        before = self.read_bytes()
        result = self.run_generator(self.models_dev)
        self.assertEqual(result.returncode, 1)
        self.assertIn("unknown models.dev provider", result.stderr)
        self.assertEqual(self.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
