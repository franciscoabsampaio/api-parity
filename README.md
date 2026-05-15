# api-parity

[![PyPI version](https://badge.fury.io/py/api-parity.svg)](https://badge.fury.io/py/api-parity)
[![PyPI version](https://badge.fury.io/py/api-parity-py.svg)](https://badge.fury.io/py/api-parity-py)
[![Crates.io](https://img.shields.io/crates/v/api-parity-rs.svg)](https://crates.io/crates/api-parity-rs)
[![Release](https://github.com/franciscoabsampaio/api-parity/actions/workflows/release.yaml/badge.svg)](https://github.com/franciscoabsampaio/api-parity/actions/workflows/release.yaml)
[![License: Apache-2.0](https://img.shields.io/badge/License-Apache2-yellow.svg)](https://opensource.org/licenses/Apache-2.0)

Cross-language API parity tracker. Diffs a **reference** API (the truth) against a **port** (another implementation) and reports what's covered, what's missing, and what's drifted. Cross-language by design — plugins emit JSON, the differ doesn't care which language produced it.

> ⚠️ **Disclaimer.** As a stark exception to the rest of my work, this project, while designed by a human, was almost entirely vibe-coded. I made this decision due to the low-criticality nature of the use case: `api-parity` doesn't run in production - it's a development tool. *And yet*, most code was still reviewed by a human. Hope you find it useful.

## Install

```bash
pip install api-parity        # the differ — runs `compare`
pip install api-parity-py     # Python plugin — walker + decorators
cargo install api-parity-rs   # Rust plugin CLI (library users add it as a Cargo dep)
```

## Quick start

The canonical case: a Rust port mirroring a Python reference API.

```bash
api-parity-py reference pyspark.sql.connect -o ref.json
api-parity-rs port      path/to/my-crate    -o port.json
api-parity   compare    ref.json port.json  -o report.md
```

`report.md` lists per-class coverage, surfaces stale port paths (typos, removed APIs), and renders per-method status. See the *Usage by direction* section below for the annotation setup.

## Usage by direction

Both plugins support `kind ∈ {reference, port}` and `mode ∈ {walker, annotation}` — four combinations per side, picked independently. Pick the section that matches what you're comparing:

<details>
<summary><strong>Rust port against Python reference</strong> — annotate a Rust crate, diff against PySpark or any Python library</summary>

In your Rust crate:

```toml
# Cargo.toml
[dependencies]
api-parity-rs = { version = "0.0.2", default-features = false }

[[bin]]
name = "api-parity-dump"
path = "src/bin/api-parity-dump.rs"
```

```rust
// src/lib.rs
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

Then diff:

```bash
api-parity-py reference pyspark.sql.connect -o ref.json
api-parity-rs port      path/to/my-crate    -o port.json
api-parity   compare    ref.json port.json
```

</details>

<details>
<summary><strong>Python port against Python reference</strong> — annotate a Python library, or diff two libraries without annotating either</summary>

**Annotated.** Decorators mirror the Rust attribute macros:

```python
from api_parity_py import parity, parity_impl, Status

@parity_impl(path="pyspark.sql.session.SparkSession", status=Status.IMPLEMENTED)
class SparkSession:
    @parity(path=".sql", status=Status.IMPLEMENTED, since="3.4")
    def sql(self, query): ...

    @parity(path=".stop", status=Status.UNIMPLEMENTED, comment="no shutdown hook yet")
    def stop(self): ...
```

```bash
api-parity-py reference pyspark.sql.connect -o ref.json
api-parity-py port      mylib                -o port.json
api-parity   compare    ref.json port.json
```

**Unannotated.** Walker on both sides — every walked public API on the port side counts as `implemented`:

```bash
api-parity-py reference pyspark.sql.connect    -o ref.json
api-parity-py port --mode=walker mylib         -o port.json
api-parity   compare ref.json port.json
```

</details>

<details>
<summary><strong>Rust crate against another Rust crate</strong> — track API drift between two Rust libraries</summary>

Walker mode on both sides — no annotations needed. Requires nightly Rust at runtime:

```bash
rustup toolchain install nightly
cargo install api-parity-rs --features walker
```

```bash
api-parity-rs reference path/to/crate-a -o ref.json    # default mode = walker
api-parity-rs port      path/to/crate-b -o port.json   # default mode = annotation
api-parity   compare    ref.json port.json
```

If neither side is annotated, drive both with `--mode=walker`. The walker shells out to `cargo +nightly rustdoc --output-format json` and parses with [`public-api`](https://crates.io/crates/public-api).

</details>

<details>
<summary><strong>Python port against Rust reference</strong> — annotate Python code that mirrors a Rust crate's surface</summary>

```bash
api-parity-rs reference path/to/rust-crate -o ref.json   # nightly required
api-parity-py port      mylib              -o port.json
api-parity   compare    ref.json port.json
```

⚠️ **Path-scheme caveat.** Rust paths use `::` and Python paths use `.`. The differ joins on the raw `path` string, so cross-language pairs need both sides to agree on a convention — typically you'd write the Python decorators with Rust-style paths:

```python
@parity(path="mycrate::Session::sql", status=Status.IMPLEMENTED)
def sql(self, q): ...
```

A future `api-parity-ai` plugin is planned to handle translation between path schemes.

</details>

## How it works

Plugins emit JSON envelopes (one of `kind = reference` or `kind = port`). The differ left-joins port entries onto reference entries by `path` and renders a report. `mode` is a *producer-side* choice (walking the public API surface vs. collecting code annotations) and is orthogonal to `kind`.

For the wire format see [`SCHEMA.md`](SCHEMA.md). For plugin authorship see [`CONTRIBUTING.md`](CONTRIBUTING.md).

## Layout

- [`api-parity/`](api-parity/) — the differ (`api-parity compare`)
- [`api-parity-py/`](api-parity-py/) — Python plugin (walker + decorators)
- [`api-parity-rs/`](api-parity-rs/) — Rust plugin (workspace: `api-parity-rs` + `api-parity-rs-macros`)

## Status

See [`CHANGELOG.md`](CHANGELOG.md). 0.0.2 ships walker/annotation symmetry on both plugins, so all four directions in the *Usage* section are supported.
