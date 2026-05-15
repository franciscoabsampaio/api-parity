//! End-to-end acceptance test for `api-parity-rs port <crate>`.
//!
//! Drives the built CLI binary (`$CARGO_BIN_EXE_api-parity-rs`) against
//! a fixture crate at `tests/fixtures/portcrate/`, which:
//!   - is its own Cargo workspace (so the parent workspace doesn't
//!     try to absorb it),
//!   - depends on `api-parity-rs` via path with `features = ["serde"]`,
//!   - ships `src/bin/api-parity-dump.rs` to feed the CLI's
//!     `cargo run --bin api-parity-dump` driver.
//!
//! The test parses the JSON envelope that lands on stdout and asserts
//! the schema-level shape — the macro round-trip is covered separately
//! by `tests/macros.rs`; here we're proving the full chain
//! (CLI → cargo run → annotated lib → dump_to_writer → stdout) works.

use std::path::PathBuf;
use std::process::Command;

fn fixture_manifest() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("..")
        .join("..")
        .join("tests")
        .join("fixtures")
        .join("portcrate")
}

#[test]
fn cli_port_annotation_emits_envelope_from_fixture_crate() {
    let cli = env!("CARGO_BIN_EXE_api-parity-rs");
    let fixture = fixture_manifest();
    assert!(
        fixture.join("Cargo.toml").exists(),
        "fixture crate missing at {}",
        fixture.display(),
    );

    let out = Command::new(cli)
        .args(["port"])
        .arg(&fixture)
        .output()
        .expect("failed to spawn api-parity-rs CLI");

    assert!(
        out.status.success(),
        "CLI exited {:?}\nstderr:\n{}",
        out.status.code(),
        String::from_utf8_lossy(&out.stderr),
    );

    let env: serde_json::Value = serde_json::from_slice(&out.stdout)
        .expect("CLI stdout was not valid JSON");

    assert_eq!(env["schema_version"], 1);
    assert_eq!(env["kind"], "port");
    assert_eq!(env["language"], "rust");
    assert_eq!(env["source"], "portcrate");

    let entries = env["entries"].as_array().expect("entries array");
    let paths: Vec<&str> = entries.iter().map(|e| e["path"].as_str().unwrap()).collect();
    assert!(paths.contains(&"ext.widget.Widget"), "got: {paths:?}");
    assert!(paths.contains(&"ext.widget.Widget.foo"), "got: {paths:?}");
    assert!(paths.contains(&"ext.widget.Widget.bar"), "got: {paths:?}");
    assert!(paths.contains(&"ext.free.solo"), "got: {paths:?}");

    for w in entries.windows(2) {
        assert!(
            w[0]["path"].as_str().unwrap() <= w[1]["path"].as_str().unwrap(),
            "entries must be sorted by path",
        );
    }
}
