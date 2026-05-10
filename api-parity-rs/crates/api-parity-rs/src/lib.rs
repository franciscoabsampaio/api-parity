//! Runtime types for the api-parity-rs port plugin.
//!
//! # How it works
//!
//! 1. Source code is annotated with `#[parity_impl]` (on `impl` blocks)
//!    or `#[parity(...)]` (on free functions). Those macros live in
//!    `api-parity-rs-macros` and are re-exported below.
//! 2. Each annotation expands to an `inventory::submit! { ParityEntry { ... } }`
//!    call. The `inventory` crate uses link-time registration: each
//!    `submit!` drops a static into a special section, and
//!    `inventory::iter::<T>()` walks them at runtime. No central registry,
//!    no init order, and the stub fn the attribute is attached to never
//!    has to be called for the entry to be registered.
//! 3. A target-crate binary calls `dump_to_writer` (gated on the `serde`
//!    feature) to serialize the registered entries as a `kind=port`
//!    envelope (per `SCHEMA.md`) for `api-parity` to consume.
//!
//! The crate is intentionally domain-agnostic: `ParityEntry::path` is
//! just an opaque string. It can name a PySpark API, a REST endpoint, etc.

// Re-exported so the macros can refer to `::api_parity_rs::inventory::submit!`
// without users having to add `inventory` as a direct dependency.
pub use inventory;
pub use api_parity_rs_macros::{parity, parity_impl};

/// Implementation state of a tracked API.
///
/// `Unimplemented` is special-cased by the macros: it requires a `comment`
/// explaining *why* the stub exists, so reviewers get context at the call site.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Status {
    Implemented,
    Partial,
    Unimplemented,
}

impl Status {
    pub fn as_str(&self) -> &'static str {
        match self {
            Status::Implemented => "implemented",
            Status::Partial => "partial",
            Status::Unimplemented => "unimplemented",
        }
    }
}

/// One row in the port-side inventory. All fields are `&'static str` so
/// the struct can be built in `inventory::submit!` (which requires a
/// `const`-constructible value).
#[derive(Debug)]
pub struct ParityEntry {
    /// Reference path being mirrored (e.g. `"pyspark.sql.session.SparkSession.sql"`).
    /// Must match a `path` on the reference side for the join to count.
    pub path: &'static str,
    /// Local symbol path (e.g. `"SparkSession::sql"`). Built by the macros
    /// from `Self` + fn name (impl block) or `module_path!() ++ "::" ++ fn`
    /// (free fn).
    pub implementation: &'static str,
    pub status: Status,
    /// Opaque version string set by the user (e.g. `"3.5"`). Not interpreted
    /// by this crate.
    pub since: Option<&'static str>,
    /// Free-form note. Required when `status == Unimplemented`.
    pub comment: Option<&'static str>,
    /// Tracker issue number (e.g. GitHub issue #42).
    pub issue: Option<u32>,
}

// Tells `inventory` that `ParityEntry` is a collected type; this is what
// makes `inventory::iter::<ParityEntry>()` work in downstream binaries.
inventory::collect!(ParityEntry);

#[cfg(feature = "serde")]
mod dump {
    //! JSON serialization, gated on `serde` so target crates that just
    //! want to register entries don't pay the serde compile cost.

    use super::*;
    use serde::Serialize;
    use std::io::Write;

    /// Wire-format DTO for a single entry (matches SCHEMA.md `port` shape).
    /// Local to this module so the public `ParityEntry` stays serde-free.
    #[derive(Serialize)]
    struct EntryDto<'a> {
        path: &'a str,
        implementation: &'a str,
        status: &'a str,
        since: Option<&'a str>,
        issue: Option<u32>,
        comment: Option<&'a str>,
    }

    /// Wire-format envelope. `schema_version` is bumped when the contract
    /// breaks; `kind` is hard-coded to `"port"` because that's the only
    /// thing this crate produces.
    #[derive(Serialize)]
    struct Envelope<'a> {
        schema_version: u32,
        kind: &'a str,
        language: &'a str,
        version: &'a str,
        source: &'a str,
        entries: Vec<EntryDto<'a>>,
    }

    /// Serialize all registered `ParityEntry` values as a `kind=port`
    /// envelope (per SCHEMA.md) to `out`.
    ///
    /// Typical usage from a target crate:
    ///
    /// ```ignore
    /// fn main() {
    ///     api_parity_rs::dump_to_writer(
    ///         env!("CARGO_PKG_NAME"),
    ///         env!("CARGO_PKG_VERSION"),
    ///         std::io::stdout(),
    ///     ).unwrap();
    /// }
    /// ```
    pub fn dump_to_writer<W: Write>(
        source: &str,
        version: &str,
        mut out: W,
    ) -> Result<(), std::io::Error> {
        // Sort by `path` for stable output — the JSON is part of the
        // contract, and stability matters when diffing two versions.
        let mut entries: Vec<&ParityEntry> = inventory::iter::<ParityEntry>.into_iter().collect();
        entries.sort_by_key(|e| e.path);

        let envelope = Envelope {
            schema_version: 1,
            kind: "port",
            language: "rust",
            version,
            source,
            entries: entries
                .iter()
                .map(|e| EntryDto {
                    path: e.path,
                    implementation: e.implementation,
                    status: e.status.as_str(),
                    since: e.since,
                    issue: e.issue,
                    comment: e.comment,
                })
                .collect(),
        };

        // `serde_json::Error` doesn't impl `Into<std::io::Error>`, so we
        // do the conversion manually to keep the public signature clean.
        let s = serde_json::to_string_pretty(&envelope)
            .map_err(|e| std::io::Error::new(std::io::ErrorKind::Other, e))?;
        writeln!(out, "{s}")
    }
}

#[cfg(feature = "serde")]
pub use dump::dump_to_writer;
