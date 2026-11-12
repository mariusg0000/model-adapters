# Project: model-adapters

Project Status: development
Versioning: none

## Project and User Directives and Rules (Mandatory)

- `model_adapters.json` is the single source of truth, consumed by BlazeAI and FluxAI. Run
  `python3 scripts/validate.py model_adapters.json` before every push; there is no CI.
- This repository is the only place where model data is added or changed. FluxAI and BlazeAI
  never edit it and never keep their own model facts; a model change starts here.
- A new protocol value needs support in the consumers first: both reject an unknown protocol.
- No endpoint, URL, or credential fields in the catalog.
- Every content change increments `revision`; breaking schema changes bump `schema_version` and
  must be coordinated with both consumers.

## Overview

Public data-only repository (MIT) with the model/protocol catalog. Schema: `README.md`.

## Operating Model

Applications fetch the raw file over HTTPS (ETag), validate the fields they use, and cache the
last valid copy. Both resolve their models from it: FluxAI hub sources name only a catalog model
and a reasoning level, and the relay takes protocol, `max_tokens`, levels, and Lite from here.

Add a model: add the entry under its provider (exact id, `tools`, `reasoning`, `protocol` when it
differs from `default_protocol`, `anthropic.max_tokens` for Messages models), increment
`revision`, validate, commit, push. Values come from provider documentation or models.dev, not
from live guarantees.

## Source Authority

`README.md` defines the schema; `scripts/validate.py` enforces it.

## Project Map

- `model_adapters.json` — the catalog.
- `scripts/validate.py` — strict local validator (stdlib).
