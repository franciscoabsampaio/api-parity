//! Integration tests for `#[parity]` / `#[parity_impl]` and the
//! serde-gated `dump_to_writer`.
//!
//! Every type and fn in this file exists solely as a host for an attribute
//! macro — the macro's job is to register an `inventory::submit!` entry at
//! link time, not to generate runtime calls. Nothing here is ever invoked,
//! hence the file-wide `dead_code` allow.
//!
//! `inventory` collects entries from the *whole* test binary into one
//! global iterator, so each test filters by a unique `path` prefix to
//! stay independent of the others.

#![allow(dead_code)]

use api_parity_rs_core::{parity, parity_impl, ParityEntry, Status};

// ---------------------------------------------------------------------------
// Test 1 — parity_impl with a parent path.
//
// Verifies the two headline behaviors of `#[parity_impl]`:
//   (a) when both `path` and `status` are set on the impl, a class-level
//       entry is registered with `implementation = "<TypeName>"`;
//   (b) child `#[parity(path = ".child", ...)]` annotations get their
//       leading `.` rewritten to `<parent_path>.<child>` at expansion time,
//       producing a single `&'static str` literal in the registered entry
//       (no runtime concat).
// Also exercises the optional fields `since`, `comment`, `issue`, and the
// rule that `Unimplemented` requires a `comment` (the `baz` case).
// ---------------------------------------------------------------------------

struct Widget;

#[parity_impl(path = "ext.widget.Widget", status = Implemented, since = "1.0")]
impl Widget {
    #[parity(path = ".foo", status = Implemented)]
    fn foo(&self) {}

    #[parity(path = ".bar", status = Partial, comment = "missing batch mode")]
    fn bar(&self) {}

    #[parity(path = ".baz", status = Unimplemented, comment = "todo", issue = 42)]
    fn baz(&self) {}
}

#[test]
fn parity_impl_registers_class_and_relative_children() {
    let prefix = "ext.widget.Widget";
    let entries: Vec<&ParityEntry> = inventory::iter::<ParityEntry>
        .into_iter()
        .filter(|e| e.path.starts_with(prefix))
        .collect();

    // Expect 4 entries: the class itself + foo, bar, baz.
    let paths: Vec<&str> = entries.iter().map(|e| e.path).collect();
    assert!(paths.contains(&"ext.widget.Widget"));
    assert!(paths.contains(&"ext.widget.Widget.foo"));
    assert!(paths.contains(&"ext.widget.Widget.bar"));
    assert!(paths.contains(&"ext.widget.Widget.baz"));
    assert_eq!(entries.len(), 4);

    // Class-level entry: implementation is the bare type name, optional
    // fields propagate from the impl-level args.
    let class = entries
        .iter()
        .find(|e| e.path == "ext.widget.Widget")
        .unwrap();
    assert_eq!(class.implementation, "Widget");
    assert_eq!(class.status, Status::Implemented);
    assert_eq!(class.since, Some("1.0"));

    // Child with no comment: confirms `comment = None` is preserved (i.e.
    // the macro doesn't accidentally fill it in from the parent).
    let foo = entries
        .iter()
        .find(|e| e.path == "ext.widget.Widget.foo")
        .unwrap();
    assert_eq!(foo.implementation, "Widget::foo");
    assert_eq!(foo.status, Status::Implemented);
    assert_eq!(foo.comment, None);

    // Unimplemented entry: comment is required (enforced by the macro), and
    // the optional `issue` field round-trips as a `u32`.
    let baz = entries
        .iter()
        .find(|e| e.path == "ext.widget.Widget.baz")
        .unwrap();
    assert_eq!(baz.status, Status::Unimplemented);
    assert_eq!(baz.comment, Some("todo"));
    assert_eq!(baz.issue, Some(42));
}

// ---------------------------------------------------------------------------
// Test 2 — parity_impl with no args.
//
// When the impl block carries no `path`/`status`, no class-level entry is
// registered, but children with *absolute* paths (no leading `.`) still
// work and inherit the `Self::fn` implementation prefix from the impl.
// This is the "I just want to annotate a few methods, the type isn't part
// of the parity surface" case.
// ---------------------------------------------------------------------------

struct Naked;

#[parity_impl]
impl Naked {
    #[parity(path = "ext.naked.absolute_only", status = Implemented)]
    fn whatever(&self) {}
}

#[test]
fn parity_impl_without_parent_path_registers_absolute_child() {
    let entries: Vec<&ParityEntry> = inventory::iter::<ParityEntry>
        .into_iter()
        .filter(|e| e.path.starts_with("ext.naked."))
        .collect();
    assert_eq!(entries.len(), 1, "no class-level entry should appear");
    let e = entries[0];
    assert_eq!(e.path, "ext.naked.absolute_only");
    assert_eq!(e.implementation, "Naked::whatever");
}

// ---------------------------------------------------------------------------
// Test 3 — #[parity] on a free function.
//
// Without an enclosing impl block to provide a type prefix, the macro
// builds the implementation path from `module_path!()::fn_name`. We can't
// hard-code the module path because integration tests run as their own
// crate (binary name `macros` here), so we only assert the `::solo` suffix.
// ---------------------------------------------------------------------------

#[parity(path = "ext.free.solo", status = Partial, comment = "wip")]
fn solo() {}

#[test]
fn parity_on_free_fn_uses_module_path() {
    let e = inventory::iter::<ParityEntry>
        .into_iter()
        .find(|e| e.path == "ext.free.solo")
        .expect("entry should be registered");
    assert!(
        e.implementation.ends_with("::solo"),
        "implementation = {}",
        e.implementation,
    );
    assert_eq!(e.status, Status::Partial);
    assert_eq!(e.comment, Some("wip"));
}

// ---------------------------------------------------------------------------
// Test 4 — dump_to_writer envelope shape (serde feature only).
//
// Exercises the only non-macro public function in the crate. Asserts the
// envelope keys match SCHEMA.md (`schema_version`, `kind = "port"`,
// `language = "rust"`, `source`, `version`, `entries`) and that entries
// come out sorted by `path` ascending — sort stability is part of the
// contract because the JSON gets diffed across versions.
// ---------------------------------------------------------------------------

#[cfg(feature = "serde")]
#[test]
fn dump_to_writer_emits_sorted_envelope() {
    use api_parity_rs_core::dump_to_writer;
    let mut buf: Vec<u8> = Vec::new();
    dump_to_writer("test-source", "9.9.9", &mut buf).unwrap();
    let s = String::from_utf8(buf).unwrap();
    let v: serde_json::Value = serde_json::from_str(&s).unwrap();

    assert_eq!(v["schema_version"], 1);
    assert_eq!(v["kind"], "port");
    assert_eq!(v["language"], "rust");
    assert_eq!(v["source"], "test-source");
    assert_eq!(v["version"], "9.9.9");

    let arr = v["entries"].as_array().unwrap();
    // 4 from Widget + 1 from Naked + 1 from solo = 6 minimum.
    assert!(arr.len() >= 6, "expected ≥6 entries, got {}", arr.len());
    for w in arr.windows(2) {
        assert!(
            w[0]["path"].as_str().unwrap() <= w[1]["path"].as_str().unwrap(),
            "entries must be sorted by path",
        );
    }
}
