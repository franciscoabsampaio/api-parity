// `use ... as _;` forces the linker to keep portcrate's lib symbols,
// which is what makes the lib's `inventory::submit!` items visible to
// `dump_to_writer` (link-time registration only works if the crate
// gets linked).
use portcrate as _;

fn main() -> std::io::Result<()> {
    api_parity_rs::dump_to_writer(
        env!("CARGO_PKG_NAME"),
        env!("CARGO_PKG_VERSION"),
        std::io::stdout(),
    )
}
