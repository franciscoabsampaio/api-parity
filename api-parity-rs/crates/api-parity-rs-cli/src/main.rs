//! `api-parity-rs <kind> <target> [-o PATH | -]`
//!
//! Thin wrapper that delegates to `cargo run --bin api-parity-dump
//! --manifest-path <target>/Cargo.toml`. The target crate is expected to
//! ship a bin named `api-parity-dump` whose body is one call to
//! `api_parity_rs_core::dump_to_writer` — see CONTRIBUTING.md.
//!
//! Only `kind = port` is supported; reference-side scanning of a Rust crate
//! would be a separate plugin (e.g. via rustdoc-json) and isn't in scope.

use std::path::PathBuf;
use std::process::{Command, ExitCode};

use clap::{Parser, ValueEnum};

const EXIT_USAGE: u8 = 64;

#[derive(Parser)]
#[command(name = "api-parity-rs", about, version)]
struct Args {
    /// `port` is the only supported kind today.
    kind: Kind,

    /// Path to the target Rust crate (containing a `Cargo.toml`).
    target: PathBuf,

    /// Output path, or `-` for stdout.
    #[arg(short = 'o', long, default_value = "-")]
    output: String,

    /// Name of the dump bin in the target crate.
    #[arg(long, default_value = "api-parity-dump")]
    bin: String,
}

#[derive(Copy, Clone, ValueEnum)]
enum Kind {
    Reference,
    Port,
}

fn main() -> ExitCode {
    let args = Args::parse();

    if !matches!(args.kind, Kind::Port) {
        eprintln!("api-parity-rs: kind=reference is not yet implemented");
        return ExitCode::from(EXIT_USAGE);
    }

    let manifest = args.target.join("Cargo.toml");
    if !manifest.exists() {
        eprintln!(
            "api-parity-rs: no Cargo.toml at {} — is `{}` a crate path?",
            manifest.display(),
            args.target.display(),
        );
        return ExitCode::from(1);
    }

    let result = Command::new("cargo")
        .args(["run", "--quiet", "--release", "--bin", &args.bin, "--manifest-path"])
        .arg(&manifest)
        .output();

    let out = match result {
        Ok(o) => o,
        Err(e) => {
            eprintln!("api-parity-rs: failed to invoke cargo: {e}");
            return ExitCode::from(1);
        }
    };

    if !out.status.success() {
        eprintln!("{}", String::from_utf8_lossy(&out.stderr));
        return ExitCode::from(out.status.code().unwrap_or(1) as u8);
    }

    let write_result = if args.output == "-" {
        use std::io::Write;
        std::io::stdout().write_all(&out.stdout)
    } else {
        std::fs::write(&args.output, &out.stdout)
    };
    if let Err(e) = write_result {
        eprintln!("api-parity-rs: failed to write output: {e}");
        return ExitCode::from(1);
    }
    ExitCode::SUCCESS
}
