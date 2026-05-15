//! Minimal public-API surface for the walker acceptance test.

/// Public struct → `kind: "class"`.
pub struct Session;

impl Session {
    /// Method on a type → `kind: "method"`.
    pub fn sql(&self, _query: &str) -> i32 {
        0
    }

    pub fn close(self) {}
}

/// Free function → `kind: "function"`.
pub fn helper() -> i32 {
    1
}

/// Public constant → `kind: "property"`.
pub const VERSION: &str = "0.1.0";

// Private item: must not appear in the walker output.
fn _private_helper() {}
