# api-parity

[![PyPI version](https://badge.fury.io/py/api-parity.svg)](https://badge.fury.io/py/api-parity)
[![PyPI version](https://badge.fury.io/py/api-parity-py.svg)](https://badge.fury.io/py/api-parity-py)
[![Release](https://github.com/franciscoabsampaio/api-parity/actions/workflows/release.yaml/badge.svg)](https://github.com/franciscoabsampaio/api-parity/actions/workflows/release.yaml)
[![Crates.io](https://img.shields.io/crates/v/api-parity-rs.svg)](https://crates.io/crates/api-parity-rs)
[![License: Apache-2.0](https://img.shields.io/badge/License-Apache2-yellow.svg)](https://opensource.org/licenses/Apache-2.0)

`api-parity` provides a consistent way of comparing a **reference** API (the truth) against a **port** (another implementation). Because `api-parity`'s unit of measure is language-agnostic (JSON files), it can easily compare cross-language, and report what's covered, what's missing, and what's drifted.

All it requires is the right plugins (for each language), and the port's members (classes, properties, methods) to be annotated.

> ⚠️ **Disclaimer:** As a stark exception to the rest of my work,
this project, while designed by a human, was almost entirely vibe-coded.
I made this decision due to the low-criticality nature of the use case:
`api-parity` doesn't run in production - it's a simple tool to assist during development. *And yet*, most code was still reviewed by a human. Hope you find it useful.

## Layout

- **`api-parity/`** — Python CLI (`api-parity compare`). Knows nothing about any
  particular language; just left-joins two JSON inventories on `path` and
  renders a report.
- **`api-parity-py/`** — Reference plugin for Python. Walks a Python package and
  emits the public API surface.
- **`api-parity-rs/`** — Port plugin for Rust. Two crates: `api-parity-rs`
  (runtime types + `dump_to_writer` + a CLI that drives
  `cargo run --bin  api-parity-dump` on the target crate) and `api-parity-rs-macros`
  (the `#[parity]` / `#[parity_impl]` attribute proc-macros, kept separate
  because `proc-macro = true` crates can't ship anything else).

## Wire format

Plugins talk to core via JSON. See [`SCHEMA.md`](SCHEMA.md).

## Example

End-to-end: comparing a Rust port against the public PySpark Connect API.

**1. Annotate the Rust target.** In your crate, depend on `api-parity-rs`,
mark the APIs you mirror with `#[parity_impl]` /
`#[parity]`, and add a 3-line `src/bin/api-parity-dump.rs`:

```toml
# Cargo.toml
[dependencies]
api-parity-rs = { version = "0.0.2", default-features = false }
```

```rust
use api_parity_rs::{parity, parity_impl};

#[parity_impl(path = "pyspark.sql.session.SparkSession", status = Implemented)]
impl SparkSession {
    #[parity(path = ".sql", status = Implemented, since = "3.4")]
    pub fn sql(&self, query: &str) -> Result<DataFrame, SparkError> { /* … */ }

    #[parity(path = ".stop", status = Unimplemented, comment = "no shutdown hook yet", issue = 42)]
    pub fn stop(&self) -> Result<(), SparkError> { unimplemented!() }
}
```

```rust
// src/bin/api-parity-dump.rs
fn main() -> std::io::Result<()> {
    api_parity_rs::dump_to_writer(
        env!("CARGO_PKG_NAME"),
        env!("CARGO_PKG_VERSION"),
        std::io::stdout(),
    )
}
```

**2. Build both inventories and diff them:**

```bash
api-parity-py reference pyspark.sql.connect -o ref.json
api-parity-rs port      path/to/my-crate    -o port.json
api-parity   compare    ref.json  port.json -o report.md
```

`report.md` groups members under their parent class, surfaces a per-class
coverage percentage, and lists port entries whose `path` didn't resolve in
the reference (typos, removed APIs, drift).

## Status

py → rs only. Other directions later.
