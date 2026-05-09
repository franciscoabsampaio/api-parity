# api-parity

[![PyPI version](https://badge.fury.io/py/api-parity.svg)](https://badge.fury.io/py/api-parity)
[![PyPI version](https://badge.fury.io/py/api-parity-py.svg)](https://badge.fury.io/py/api-parity-py)
[![Release](https://github.com/franciscoabsampaio/api-parity/actions/workflows/release.yaml/badge.svg)](https://github.com/franciscoabsampaio/api-parity/actions/workflows/release.yaml)
[![Crates.io](https://img.shields.io/crates/v/api-parity-rs-core.svg)](https://crates.io/crates/api-parity-rs-core)
[![License: Apache-2.0](https://img.shields.io/badge/License-Apache2-yellow.svg)](https://opensource.org/licenses/Apache-2.0)

Cross-language API parity tracker. Compares a **reference** API (the truth)
against a **port** (a local implementation) and reports what's covered, what's
missing, and what's drifted.

## Layout

- **`api-parity/`** — Python CLI (`api-parity compare`). Knows nothing about any
  particular language; just left-joins two JSON inventories on `path` and
  renders a report.
- **`api-parity-py/`** — Reference plugin for Python. Walks a Python package and
  emits the public API surface.
- **`api-parity-rs/`** — Port plugin for Rust. A two-crate library
  (`api-parity-rs-core` + `api-parity-rs-macros`) that the Rust target adds as a
  dependency, plus a `dump_to_writer` helper the user calls from a thin bin.

## Wire format

Plugins talk to core via JSON. See [`SCHEMA.md`](SCHEMA.md).

## Status

py → rs only. Other directions later.
