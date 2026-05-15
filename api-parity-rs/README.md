# api-parity-rs

Rust plugin for [`api-parity`](https://github.com/franciscoabsampaio/api-parity). Provides:

- Attribute macros (`#[parity]`, `#[parity_impl]`) for annotating a Rust crate as a **port** of some upstream API.
- A reference-mode **walker** (behind the `walker` Cargo feature) that inspects another Rust crate's public surface via `cargo +nightly rustdoc`.
- A CLI bin (`api-parity-rs`) that drives both modes and emits a `kind = port` / `kind = reference` envelope per [SCHEMA.md](../SCHEMA.md).

The workspace contains two crates: `api-parity-rs` (lib + bin in one crate, gated by features) and `api-parity-rs-macros` (the proc-macros, separated because `proc-macro = true` crates can't ship anything else).

## Install

```bash
# CLI only — port-mode driver (cargo run --bin api-parity-dump under the hood):
cargo install api-parity-rs

# With reference-mode walker (rustdoc-json + public-api). Requires nightly Rust at runtime:
rustup toolchain install nightly
cargo install api-parity-rs --features walker
```

For library use (annotating a target crate), add it as a Cargo dep — see below.

## Annotating a target crate

Add the lib as a dep with the default CLI feature off; keep `serde` so the dump helper is available:

```toml
[dependencies]
api-parity-rs = { version = "0.0.2", default-features = false, features = ["serde"] }

[[bin]]
name = "api-parity-dump"
path = "src/bin/api-parity-dump.rs"
```

Annotate impls and free functions:

```rust
use api_parity_rs::{parity, parity_impl};

#[parity_impl(path = "pyspark.sql.session.SparkSession", status = Implemented)]
impl SparkSession {
    #[parity(path = ".sql", status = Implemented, since = "3.4")]
    pub fn sql(&self, query: &str) -> Result<DataFrame, SparkError> { /* … */ }

    #[parity(path = ".stop", status = Unimplemented, comment = "no shutdown hook yet")]
    pub fn stop(&self) -> Result<(), SparkError> { unimplemented!() }
}
```

Add a 3-line bin that serializes the registered entries:

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

A leading `.` in a child `path` is rewritten to `<parent>.<child>` at macro-expansion time. `Status::Unimplemented` requires a `comment`.

## CLI usage

```bash
api-parity-rs <kind> [--mode walker|annotation] <crate-path> [-o PATH | -]
```

- `kind`: `port` or `reference`.
- `--mode`: defaults to `annotation` for `port`, `walker` for `reference`.
- `<crate-path>`: directory containing the target `Cargo.toml`.
- `-o`: output file, or `-` for stdout (default).

<details>
<summary>Example — port mode (annotated Rust target)</summary>

```bash
api-parity-rs port path/to/target-crate -o port.json
```

Drives `cargo run --bin api-parity-dump --manifest-path <target>/Cargo.toml` and forwards stdout. The target crate must define `src/bin/api-parity-dump.rs` (see *Annotating a target crate* above).

</details>

<details>
<summary>Example — reference mode (walker, no annotations needed)</summary>

```bash
api-parity-rs reference path/to/any-crate -o ref.json
```

Shells out to `cargo +nightly rustdoc --output-format json` (via [`rustdoc-json`](https://crates.io/crates/rustdoc-json)) and parses the result with [`public-api`](https://crates.io/crates/public-api). Requires `--features walker` at install time and a nightly toolchain at runtime.

</details>

## Cargo features

| Feature  | Default | What it adds |
| -------- | ------- | ------------ |
| `cli`    | yes     | The `api-parity-rs` CLI bin (depends on `clap`). |
| `serde`  |         | `dump_to_writer` JSON helper (depends on `serde` + `serde_json`). |
| `walker` |         | Reference-mode walker (depends on `public-api` + `rustdoc-json`, implies `cli` + `serde`). |

Target crates that only annotate set `default-features = false, features = ["serde"]` to avoid the CLI / clap compile cost.

## Pipelines

```bash
# Python reference ↔ Rust port (the canonical case):
api-parity-py reference pyspark.sql.connect -o ref.json
api-parity-rs port      path/to/target      -o port.json
api-parity   compare    ref.json port.json

# Rust ↔ Rust (no annotations needed on either side):
api-parity-rs reference path/to/crate-a -o ref.json
api-parity-rs port      path/to/crate-b -o port.json
api-parity   compare    ref.json port.json
```
