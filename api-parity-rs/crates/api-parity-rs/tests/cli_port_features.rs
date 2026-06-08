//! Verifies the CLI forwards `--features` to the `cargo run` it spawns
//! against the target crate. The `portcrate` fixture gates an extra
//! annotation behind a `gated` Cargo feature; with the flag, the dump
//! envelope must contain it.

use std::path::PathBuf;
use std::process::Command;

fn fixture() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("..")
        .join("..")
        .join("tests")
        .join("fixtures")
        .join("portcrate")
}

#[test]
fn cli_forwards_features_to_cargo_run() {
    let cli = env!("CARGO_BIN_EXE_api-parity-rs");
    let out = Command::new(cli)
        .args(["port"])
        .arg(fixture())
        .args(["--features", "gated"])
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
    let paths: Vec<&str> = env["entries"]
        .as_array()
        .expect("entries array")
        .iter()
        .map(|e| e["path"].as_str().unwrap())
        .collect();
    assert!(
        paths.contains(&"ext.gated.only"),
        "feature-gated entry missing — `--features` was not forwarded. got: {paths:?}",
    );
}
