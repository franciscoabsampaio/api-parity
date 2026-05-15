//! `api-parity-rs <kind> [--mode walker|annotation] <target> [-o PATH | -]`
//!
//! - `port` (default mode `annotation`): drives `cargo run --bin
//!   api-parity-dump --manifest-path <target>/Cargo.toml`. The target crate
//!   ships a 3-line bin that calls `api_parity_rs::dump_to_writer`.
//! - `reference` (default mode `walker`, only when built with the `walker`
//!   feature): runs `cargo +nightly rustdoc --output-format json` on the
//!   target via the `rustdoc-json` crate, parses with `public-api`, and
//!   emits a `kind=reference` envelope.

use std::path::PathBuf;
use std::process::{Command, ExitCode};

use clap::{Parser, ValueEnum};

const EXIT_USAGE: u8 = 64;

#[derive(Parser)]
#[command(name = "api-parity-rs", about, version)]
struct Args {
    /// `reference` (walker) or `port` (annotation).
    kind: Kind,

    /// Path to the target Rust crate (containing a `Cargo.toml`).
    target: PathBuf,

    /// How entries are produced. Defaults: reference → walker, port → annotation.
    #[arg(long)]
    mode: Option<Mode>,

    /// Output path, or `-` for stdout.
    #[arg(short = 'o', long, default_value = "-")]
    output: String,

    /// Name of the dump bin in the target crate (only used in port + annotation mode).
    #[arg(long, default_value = "api-parity-dump")]
    bin: String,
}

#[derive(Copy, Clone, ValueEnum)]
enum Kind {
    Reference,
    Port,
}

#[derive(Copy, Clone, ValueEnum, PartialEq, Eq)]
enum Mode {
    Walker,
    Annotation,
}

fn main() -> ExitCode {
    let args = Args::parse();
    let mode = args.mode.unwrap_or(default_mode(args.kind));

    let manifest = args.target.join("Cargo.toml");
    if !manifest.exists() {
        eprintln!(
            "api-parity-rs: no Cargo.toml at {} — is `{}` a crate path?",
            manifest.display(),
            args.target.display(),
        );
        return ExitCode::from(1);
    }

    let payload = match (args.kind, mode) {
        (Kind::Port, Mode::Annotation) => run_dump_bin(&manifest, &args.bin),
        (Kind::Reference, Mode::Walker) => run_walker(&manifest),
        (Kind::Port, Mode::Walker) => Err((
            EXIT_USAGE,
            "kind=port mode=walker is not yet implemented".into(),
        )),
        (Kind::Reference, Mode::Annotation) => Err((
            EXIT_USAGE,
            "kind=reference mode=annotation is not yet implemented".into(),
        )),
    };

    match payload {
        Ok(bytes) => write_output(&args.output, &bytes),
        Err((code, msg)) => {
            eprintln!("api-parity-rs: {msg}");
            ExitCode::from(code)
        }
    }
}

fn default_mode(kind: Kind) -> Mode {
    match kind {
        Kind::Reference => Mode::Walker,
        Kind::Port => Mode::Annotation,
    }
}

fn run_dump_bin(manifest: &std::path::Path, bin: &str) -> Result<Vec<u8>, (u8, String)> {
    let result = Command::new("cargo")
        .args(["run", "--quiet", "--release", "--bin", bin, "--manifest-path"])
        .arg(manifest)
        .output();
    let out = result.map_err(|e| (1, format!("failed to invoke cargo: {e}")))?;
    if !out.status.success() {
        return Err((
            out.status.code().unwrap_or(1) as u8,
            String::from_utf8_lossy(&out.stderr).into_owned(),
        ));
    }
    Ok(out.stdout)
}

#[cfg(feature = "walker")]
fn run_walker(manifest: &std::path::Path) -> Result<Vec<u8>, (u8, String)> {
    use api_parity_rs::walk;
    let entries = walk::walk_crate(manifest).map_err(|e| (1, e.to_string()))?;
    let crate_name = read_crate_name(manifest).unwrap_or_else(|| "?".to_string());
    let crate_version = read_crate_version(manifest);
    let envelope = serde_json::json!({
        "schema_version": 1,
        "kind": "reference",
        "language": "rust",
        "version": crate_version,
        "source": crate_name,
        "entries": entries,
    });
    let mut s = serde_json::to_string_pretty(&envelope)
        .map_err(|e| (1, format!("serialize envelope: {e}")))?;
    s.push('\n');
    Ok(s.into_bytes())
}

#[cfg(not(feature = "walker"))]
fn run_walker(_manifest: &std::path::Path) -> Result<Vec<u8>, (u8, String)> {
    Err((
        EXIT_USAGE,
        "reference mode requires the `walker` feature \
         (rebuild with `cargo install api-parity-rs --features walker`)".into(),
    ))
}

#[cfg(feature = "walker")]
fn read_crate_name(manifest: &std::path::Path) -> Option<String> {
    let s = std::fs::read_to_string(manifest).ok()?;
    extract_toml_value(&s, "name")
}

#[cfg(feature = "walker")]
fn read_crate_version(manifest: &std::path::Path) -> Option<String> {
    let s = std::fs::read_to_string(manifest).ok()?;
    extract_toml_value(&s, "version")
}

/// Tiny TOML scraper: reads `<key> = "<value>"` from the `[package]` section.
/// Sufficient for `name`/`version` without pulling in a TOML parser.
#[cfg(feature = "walker")]
fn extract_toml_value(toml: &str, key: &str) -> Option<String> {
    let mut in_package = false;
    for line in toml.lines() {
        let line = line.trim();
        if line.starts_with('[') {
            in_package = line == "[package]";
            continue;
        }
        if !in_package {
            continue;
        }
        if let Some(rest) = line.strip_prefix(&format!("{key} ")).or_else(|| line.strip_prefix(&format!("{key}="))) {
            let rest = rest.trim_start_matches('=').trim();
            return rest
                .trim_matches(|c| c == '"' || c == '\'')
                .split('#')
                .next()
                .map(|s| s.trim().to_string())
                .filter(|s| !s.is_empty());
        }
    }
    None
}

fn write_output(output: &str, bytes: &[u8]) -> ExitCode {
    let result = if output == "-" {
        use std::io::Write;
        std::io::stdout().write_all(bytes)
    } else {
        std::fs::write(output, bytes)
    };
    match result {
        Ok(_) => ExitCode::SUCCESS,
        Err(e) => {
            eprintln!("api-parity-rs: failed to write output: {e}");
            ExitCode::from(1)
        }
    }
}
