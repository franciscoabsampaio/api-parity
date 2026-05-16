# api-parity

Language-agnostic differ for the [`api-parity`](https://github.com/franciscoabsampaio/api-parity) project. Reads two JSON envelopes (a *reference* and a *port*), left-joins them on `path`, and renders a coverage report.

See the [project README](https://github.com/franciscoabsampaio/api-parity) for end-to-end pipelines and the cross-language story.

## Install

```bash
pip install api-parity
```

## Usage

```bash
api-parity compare ref.json port.json -o report.md
# or:
api-parity compare ref.json port.json --format=json -o report.json
```

`ref.json` and `port.json` are produced by language-specific plugins:

- [`api-parity-py`](https://pypi.org/project/api-parity-py/) — Python plugin (walker + decorators).
- [`api-parity-rs`](https://crates.io/crates/api-parity-rs) — Rust plugin (attribute macros + walker).

The report groups members under their parent class, surfaces per-class coverage percentages, and lists *stale* port entries — paths the port claims but the reference doesn't have (typos, removed APIs, drift).

## Wire format

Both envelopes follow [`SCHEMA.md`](https://github.com/franciscoabsampaio/api-parity/blob/main/SCHEMA.md). The differ doesn't care which language produced them, only that `path` is a shared join key. Adding a new language means writing a plugin, not patching the differ.
