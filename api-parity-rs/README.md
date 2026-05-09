# api-parity-rs

Port-side plugin for Rust targets. Three crates:

- `api-parity-rs-core` — runtime types (`ParityEntry`, `Status`), the
  `inventory::collect!` registration, and a `dump_to_writer` helper.
- `api-parity-rs-macros` — the `#[parity]` and `#[parity_impl]` attribute macros.
- `api-parity-rs` — CLI wrapper. Drives `cargo run --bin api-parity-dump`
  on a target crate so the user-facing shape matches the other plugins
  (`api-parity-rs port <crate-path>`).

## Usage in a target crate

```toml
[dependencies]
api-parity-rs-core = { version = "0.1", features = ["serde"] }

[[bin]]
name = "api-parity-dump"
path = "src/bin/api-parity-dump.rs"
```

Annotate code:

```rust
use api_parity_rs_core::{parity, parity_impl};

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
    api_parity_rs_core::dump_to_writer(
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

If you want to keep `serde_json` out of default builds, gate the bin behind
a feature: drop `features = ["serde"]` from the dep, add a `parity` feature
that re-enables it (`parity = ["api-parity-rs-core/serde"]`), and put
`required-features = ["parity"]` on the `[[bin]]`. Then run with
`api-parity-rs port <crate> --bin api-parity-dump` plus
`CARGO_INCREMENTAL=0 cargo …` — or just always-on it for simplicity.
