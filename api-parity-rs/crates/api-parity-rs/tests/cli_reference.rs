//! End-to-end acceptance test for `api-parity-rs reference <crate>`
//! (walker mode).
//!
//! Drives the built CLI binary against `tests/fixtures/refcrate/`,
//! which is a tiny library with one of each item kind. The CLI runs
//! `cargo +nightly rustdoc --output-format json` under the hood
//! (via `rustdoc-json`) and parses the result with `public-api`, so
//! this test requires a nightly toolchain to be installed locally.
//!
//! Gated on the `walker` feature so a default `cargo test` build (no
//! walker) doesn't try to invoke nightly.

#![cfg(feature = "walker")]

use std::path::PathBuf;
use std::process::Command;

fn fixture_manifest() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("..")
        .join("..")
        .join("tests")
        .join("fixtures")
        .join("refcrate")
}

#[test]
fn cli_reference_walker_emits_envelope_from_fixture_crate() {
    let cli = env!("CARGO_BIN_EXE_api-parity-rs");
    let fixture = fixture_manifest();
    assert!(
        fixture.join("Cargo.toml").exists(),
        "fixture crate missing at {}",
        fixture.display(),
    );

    let out = Command::new(cli)
        .args(["reference"])
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
    assert_eq!(env["kind"], "reference");
    assert_eq!(env["language"], "rust");
    assert_eq!(env["source"], "refcrate");

    let entries = env["entries"].as_array().expect("entries array");
    let pairs: Vec<(&str, &str)> = entries
        .iter()
        .map(|e| (e["path"].as_str().unwrap(), e["kind"].as_str().unwrap()))
        .collect();

    // Each kind has at least one representative; we assert by-shape
    // rather than exact set so rustdoc output drift doesn't break the
    // test on every compiler bump.
    assert!(
        pairs.iter().any(|(p, k)| p.ends_with("::Session") && *k == "class"),
        "missing Session class entry; got: {pairs:?}",
    );
    assert!(
        pairs.iter().any(|(p, k)| p.ends_with("::Session::sql") && *k == "method"),
        "missing Session::sql method entry; got: {pairs:?}",
    );
    assert!(
        pairs.iter().any(|(p, k)| p.ends_with("::helper") && *k == "function"),
        "missing free fn entry; got: {pairs:?}",
    );
    assert!(
        pairs.iter().any(|(p, k)| p.ends_with("::VERSION") && *k == "property"),
        "missing const entry; got: {pairs:?}",
    );

    // Private items must not leak.
    assert!(
        !pairs.iter().any(|(p, _)| p.contains("_private_helper")),
        "private item leaked: {pairs:?}",
    );

    // Stable sort is part of the wire contract.
    for w in pairs.windows(2) {
        assert!(w[0].0 <= w[1].0, "entries must be sorted by path");
    }
}
