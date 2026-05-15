//! Reference-side walker: surfaces the public API of a Rust crate as a
//! list of `{path, kind}` entries, suitable for the `kind=reference`
//! envelope.
//!
//! Implementation: shell out to `cargo +nightly rustdoc --output-format
//! json` (via the `rustdoc-json` crate), then parse the resulting JSON
//! with `public-api`. Nightly is required at runtime; library users who
//! only annotate their crates don't pay this cost — the whole module is
//! gated behind the `walker` Cargo feature.

use std::path::Path;

use serde::Serialize;

#[derive(Debug, Clone, Serialize)]
pub struct RefEntry {
    pub path: String,
    pub kind: &'static str,
}

#[derive(Debug)]
pub enum WalkerError {
    RustdocBuild(String),
    PublicApi(String),
}

impl std::fmt::Display for WalkerError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            WalkerError::RustdocBuild(s) => write!(f, "rustdoc-json build failed: {s}"),
            WalkerError::PublicApi(s) => write!(f, "public-api failed: {s}"),
        }
    }
}

impl std::error::Error for WalkerError {}

/// Walk the public API of the crate at `manifest_path` (its `Cargo.toml`).
pub fn walk_crate(manifest_path: &Path) -> Result<Vec<RefEntry>, WalkerError> {
    let rustdoc_json = rustdoc_json::Builder::default()
        .toolchain("nightly")
        .manifest_path(manifest_path)
        .build()
        .map_err(|e| WalkerError::RustdocBuild(e.to_string()))?;

    let api = public_api::Builder::from_rustdoc_json(&rustdoc_json)
        .build()
        .map_err(|e| WalkerError::PublicApi(e.to_string()))?;

    let mut entries: Vec<RefEntry> = api
        .items()
        .filter_map(|item| classify_item(&item.to_string()))
        .collect();

    entries.sort_by(|a, b| a.path.cmp(&b.path));
    entries.dedup_by(|a, b| a.path == b.path && a.kind == b.kind);
    Ok(entries)
}

/// Classify a `public-api` item rendering into a `(path, kind)` pair.
///
/// `public-api` renders items like:
///   `pub fn crate::module::Type::method(&self) -> i32`
///   `pub struct crate::module::Foo`
///   `pub const crate::FOO: u32 = …`
///
/// We strip the visibility prefix, take the leading keyword as the kind,
/// then read everything up to the first `(`, `<`, or whitespace as the
/// path. Function paths whose second-to-last segment looks like a type
/// (uppercase first letter) are reclassified as methods.
fn classify_item(rendered: &str) -> Option<RefEntry> {
    let body = rendered.trim_start_matches("pub ").trim_start();

    let (kw, rest) = body.split_once(' ')?;
    let kind: &'static str = match kw {
        "fn" => "function",
        "struct" | "enum" | "trait" | "type" | "union" => "class",
        "const" | "static" => "property",
        // Skip modules, impl blocks, use-statements, and anything else
        // we don't have a `kind` for.
        _ => return None,
    };

    let path = take_path_with_colons(rest);
    if path.is_empty() {
        return None;
    }

    let kind = if kind == "function" && looks_like_method(&path) {
        "method"
    } else {
        kind
    };

    Some(RefEntry { path, kind })
}

/// Read the path prefix from an item-rendering tail, stopping at a
/// non-path character. Path syntax is `seg::seg::seg` where each segment
/// is alphanumeric + `_`. We allow `::` mid-path but break on `(`, `<`,
/// whitespace, or a single `:` (return-type separator).
fn take_path_with_colons(s: &str) -> String {
    let bytes = s.as_bytes();
    let mut i = 0;
    while i < bytes.len() {
        let c = bytes[i] as char;
        if c.is_alphanumeric() || c == '_' {
            i += 1;
        } else if c == ':' && i + 1 < bytes.len() && bytes[i + 1] as char == ':' {
            i += 2;
        } else {
            break;
        }
    }
    s[..i].to_string()
}

fn looks_like_method(path: &str) -> bool {
    let segments: Vec<&str> = path.split("::").collect();
    if segments.len() < 2 {
        return false;
    }
    segments[segments.len() - 2]
        .chars()
        .next()
        .is_some_and(|c| c.is_uppercase())
}

#[cfg(test)]
mod classify_tests {
    use super::*;

    #[test]
    fn fn_in_module_is_function() {
        let e = classify_item("pub fn mycrate::utils::helper() -> i32").unwrap();
        assert_eq!(e.path, "mycrate::utils::helper");
        assert_eq!(e.kind, "function");
    }

    #[test]
    fn fn_on_a_type_is_method() {
        let e = classify_item("pub fn mycrate::Session::sql(&self, q: &str)").unwrap();
        assert_eq!(e.path, "mycrate::Session::sql");
        assert_eq!(e.kind, "method");
    }

    #[test]
    fn struct_is_class() {
        let e = classify_item("pub struct mycrate::Session").unwrap();
        assert_eq!(e.path, "mycrate::Session");
        assert_eq!(e.kind, "class");
    }

    #[test]
    fn enum_and_trait_are_classes() {
        assert_eq!(classify_item("pub enum mycrate::E").unwrap().kind, "class");
        assert_eq!(classify_item("pub trait mycrate::T").unwrap().kind, "class");
    }

    #[test]
    fn const_is_property() {
        let e = classify_item("pub const mycrate::FOO: u32 = 1").unwrap();
        assert_eq!(e.path, "mycrate::FOO");
        assert_eq!(e.kind, "property");
    }

    #[test]
    fn skips_unsupported_keywords() {
        assert!(classify_item("pub mod mycrate::sub").is_none());
        assert!(classify_item("impl Foo for Bar").is_none());
    }
}
