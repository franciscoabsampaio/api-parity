# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
Each package (`api-parity`, `api-parity-py`, `api-parity-rs`) versions
independently; the entries below note which package(s) each change affects.

## Unreleased

## [0.0.3](https://github.com/franciscoabsampaio/api-parity/releases/tag/v0.0.3) - 2026-05-20

### Added

- **api-parity-rs:** `#[parity]` now attaches to a `struct`, `enum`, or
  `type` alias (previously only free functions and methods), registering
  the type itself with `implementation = <module path>::<name>`. A `type`
  alias re-exporting a foreign type is the supported way to port an
  external item you can't annotate — `pub type DataType =
  arrow_schema::DataType;` records the local alias name, keeping
  `implementation` a symbol in your own crate.
- **api-parity-rs:** CLI now accepts `-F` / `--features`,
  `--no-default-features`, and `--all-features` and forwards them to
  the `cargo run --bin api-parity-dump …` it spawns against the
  target crate. Unblocks crates that gate their dump bin (and the
  `api-parity-rs` dep itself) behind an opt-in feature.
- **api-parity:** markdown reports now carry a small attribution line
  under the title linking back to the project.

## [0.0.2](https://github.com/franciscoabsampaio/api-parity/releases/tag/v0.0.2) - 2026-05-17

Walker / annotation symmetry across both language plugins, so all four
directions (py↔py, py↔rs, rs↔py, rs↔rs) are supported.

### Added

- **api-parity-py:** `@parity`, `@parity_impl`, `@parity_ref` decorators
  mirroring the Rust attribute macros — `api-parity-py port <pkg>` now
  works against an annotated Python target.
- **api-parity-rs:** reference-mode walker behind a new `walker` Cargo
  feature. Shells out to `cargo +nightly rustdoc --output-format json`
  and parses with [`public-api`](https://crates.io/crates/public-api).
  Nightly is required at runtime, not as a dep — annotation-only users
  pay no cost.
- **Both plugins:** `--mode walker|annotation` CLI flag, with
  kind-based defaults (`reference → walker`, `port → annotation`).
- **api-parity-py:** the walker now prints a grouped stderr summary
  when submodules fail to import (e.g. missing optional deps) instead
  of silently truncating the inventory.
- **All packages:** cross-plugin end-to-end acceptance tests covering
  every supported `(kind, mode)` combination through the CLI.

### Changed

- **api-parity:** PyPI distribution renamed from `api-parity-core` to
  `api-parity`.
- **api-parity-rs:** `api-parity-rs-core` merged into `api-parity-rs`
  (single crate; CLI lives behind the default `cli` feature). Target
  crates that only annotate set `default-features = false`.
- **api-parity-rs-macros:** emitted paths changed from
  `::api_parity_rs_core::…` to `::api_parity_rs::…`.
- Release tag scheme simplified: `vX.Y.Z` (differ), `py-vX.Y.Z`
  (Python plugin), `rs-vX.Y.Z` (Rust plugin workspace).
- Unsupported `(kind, mode)` combos exit 64 with "*not yet
  implemented*" rather than "not supported" — they're roadmap items,
  not refusals.

## [0.0.1](https://github.com/franciscoabsampaio/api-parity/releases/tag/v0.0.1) - 2026-05-09

### Added

- Initial release. Supports the py-to-rs direction: Python reference
  walker (`api-parity-py reference`), Rust port annotations
  (`#[parity]` / `#[parity_impl]`), and a language-agnostic differ
  (`api-parity compare`) rendering markdown + JSON reports.
