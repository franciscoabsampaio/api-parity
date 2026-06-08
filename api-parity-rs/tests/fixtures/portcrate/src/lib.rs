//! Fixture annotated with `#[parity_impl]` / `#[parity]` so the
//! port-annotation CLI acceptance test can drive a real `cargo run`.

#![allow(dead_code)]

use api_parity_rs::{parity, parity_impl};

pub struct Widget;

#[parity_impl(path = "ext.widget.Widget", status = Implemented, since = "1.0")]
impl Widget {
    #[parity(path = ".foo", status = Implemented)]
    pub fn foo(&self) {}

    #[parity(path = ".bar", status = Partial, comment = "missing batch mode")]
    pub fn bar(&self) {}
}

#[parity(path = "ext.free.solo", status = Partial, comment = "wip")]
pub fn solo() {}

// `#[parity]` directly on a type definition: `implementation` resolves to
// `portcrate::Gizmo`.
#[parity(path = "ext.gizmo.Gizmo", status = Implemented)]
pub struct Gizmo {
    pub id: u64,
}

// `#[parity]` on a `type` alias re-exporting a foreign type. The recorded
// implementation is the local alias name (`portcrate::DataType`), not the
// backing `std::collections::HashMap`.
#[parity(path = "ext.types.DataType", status = Implemented)]
pub type DataType = std::collections::HashMap<String, String>;

#[cfg(feature = "gated")]
#[parity(path = "ext.gated.only", status = Implemented)]
pub fn gated_only() {}
