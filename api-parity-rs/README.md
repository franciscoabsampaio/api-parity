# api-parity-rs

Port-side plugin for Rust targets. Two crates:

- `api-parity-rs` — runtime types (`ParityEntry`, `Status`), the
  `inventory::collect!` registration, the `dump_to_writer` helper (behind
  the `serde` feature), and a CLI bin (behind the default `cli` feature)
  that drives `cargo run --bin api-parity-dump` on a target crate.
- `api-parity-rs-macros` — the `#[parity]` and `#[parity_impl]` attribute
  proc-macros, kept separate because `proc-macro = true` crates can't ship
  anything else.

## Installing the CLI

```bash
# Port mode only (cargo run --bin api-parity-dump under the hood):
cargo install api-parity-rs

# Plus reference-mode walking (rustdoc-json + public-api). Requires
# nightly Rust at runtime.
cargo install api-parity-rs --features walker
rustup toolchain install nightly
```

## Usage in a target crate

Add `api-parity-rs` as a library-only dep (skip the default CLI feature, keep
`serde` so the dump helper is available):

```toml
[dependencies]
api-parity-rs = { version = "0.0.2", default-features = false, features = ["serde"] }

[[bin]]
name = "api-parity-dump"
path = "src/bin/api-parity-dump.rs"
```

Annotate code:

```rust
use api_parity_rs::{parity, parity_impl};

#[parity_impl(
    path = "pyspark.sql.session.SparkSession",
    status = Implemented,
)]
impl SparkSession {
    #[parity(path = ".sql", status = Implemented, since = "3.4")]
    pub fn sql(&self, query: &str) -> ... { ... }
}
```

Add `src/bin/api-parity-dump.rs`:

```rust
fn main() -> std::io::Result<()> {
    api_parity_rs::dump_to_writer(
        env!("CARGO_PKG_NAME"),
        env!("CARGO_PKG_VERSION"),
        std::io::stdout(),
    )
}
```

## Running

End-to-end against a Python reference:

```bash
api-parity-rs port path/to/target-crate -o port.json
api-parity-py reference pyspark.sql.connect -o ref.json
api-parity compare ref.json port.json
```

End-to-end Rust ↔ Rust (compares two crates' public APIs, no
annotations needed):

```bash
api-parity-rs reference path/to/crate-a -o ref.json    # walker mode (default)
api-parity-rs port      path/to/crate-b -o port.json   # annotation mode (default)
api-parity compare ref.json port.json
```
