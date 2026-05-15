# api-parity (project context)

Cross-language API parity tracker. **Repo is fresh and unconfigured** —
not yet `git init`'d, no CI, no published packages. Scaffolded on
2026-05-06 from a working prototype that lived inside the
`spark-connect` Rust crate.

## What it is

Three pieces:

- **`api-parity/`** — Python CLI (`api-parity compare REF PORT`).
  The differ + report renderer. Knows nothing about any specific
  language; just left-joins two JSON inventories on `path`.
- **`api-parity-py/`** — Python reference plugin
  (`api-parity-py reference <pkg>`). Walks a Python package and emits
  the public-API surface as JSON.
- **`api-parity-rs/`** — Rust port plugin. A workspace with two library
  crates: `api-parity-rs` (runtime types + inventory + serde-gated
  `dump_to_writer`) and `api-parity-rs-macros` (`#[parity]` and
  `#[parity_impl]` attribute macros — names kept short on purpose).
  Target Rust crates depend on these and write a thin bin that calls
  `dump_to_writer`.

## Wire format

`SCHEMA.md` is the source of truth. Summary:

- Both sides emit `{schema_version: 1, kind, language, version, source, entries: [...]}`.
- Reference entries: `{path, kind}` where `kind ∈ {class, method, property, function}`.
- Port entries: `{path, implementation, status, since, issue, comment}`
  where `status ∈ {implemented, partial, unimplemented}`.
- `comment` lives only on port entries by design; reference truth is
  "this exists", port commentary is what the renderer surfaces.
- Plugin CLI: `api-parity-<plugin> <kind> <target> [-o PATH | -]`. Plugins
  exit 64 on unsupported `kind`s.

## Status

- **Done and exercised:** scaffolding, schema doc, `api-parity-py/walk.py`
  (real introspection ported), `api-parity/compare.py` (left-join
  differ), `api-parity/render_markdown.py` (renderer ported),
  `api-parity-rs` (full impl with serde-gated dump),
  `api-parity-rs-macros` (full impl ported, supports relative `path = ".foo"`
  via parent-prefix expansion).
- **End-to-end smoke test passes**: walking real `pyspark.sql.{connect,session}`
  yields ~1593 reference paths; the differ correctly classifies covered /
  stale / uncovered against a fake port input; markdown output groups
  members under their parent class and renders class-level status.
- **Stubs remaining**: none. Every file has working code.

## Roadmap

**0.0.2 — walker / annotation symmetry.** Reframe references and ports
as orthogonal to the production method. Default mapping stays
(`reference → walker`, `port → annotation`), but each plugin should
support both directions where feasible:

- Python: add `@parity_impl` / `@parity` decorators (mirroring the Rust
  attribute macros) so `api-parity-py port <pkg>` works. Optional
  `@reference` decorator for declarative reference inventories.
- Rust: add a walker behind a `walker` Cargo feature (so library users
  who only annotate don't pay the cost). Implementation: shell out to
  `cargo +nightly rustdoc --output-format json` and parse with the
  `rustdoc-types` / `public-api` crates. Nightly is required to *run*
  the walker, not to depend on the lib.
- CLI grammar gains `--mode walker|annotation` with kind-based
  defaults; unsupported combos exit 64.

**Future plugins.**

- `api-parity-ai` — natural-language-driven discovery (and, eventually,
  translation between path schemes). Translation should run the AI
  *after* a heuristic pass (substring / casing / module-prefix
  rewriting), so the model only handles genuinely ambiguous cases. The
  AI plugin is downstream of the schema; it produces the same
  envelopes everything else does.

**Other unblocked work.**

- Migrate `../spark-connect` off its in-tree `crates/api-parity-{core,macros}`
  onto this repo's published `api-parity-rs` + `api-parity-rs-macros`.
  Breaking rename: macro arg `reference = "..."` → `path = "..."`;
  emitted paths `::api_parity_rs::…` instead of `::api_parity_core::…`.

## Layout reference

```text
parity/                                # working dir name (not renamed)
├── CLAUDE.md                          # you are here
├── README.md                          # public-facing intro
├── SCHEMA.md                          # wire-format spec
├── api-parity/
│   ├── pyproject.toml                 # hatch, no runtime deps
│   └── src/api_parity/
│       ├── __init__.py
│       ├── __main__.py                # CLI entry (`api-parity`)
│       ├── compare.py                 # left-join + totals
│       ├── render_markdown.py
│       └── render_json.py
├── api-parity-py/
│   ├── pyproject.toml                 # hatch, no runtime deps
│   └── src/api_parity_py/
│       ├── __init__.py
│       ├── __main__.py                # CLI entry (`api-parity-py`); only `reference` kind supported
│       └── walk.py                    # the introspection
└── api-parity-rs/
    ├── Cargo.toml                     # workspace
    ├── README.md                      # consumer guide
    └── crates/
        ├── api-parity-rs/        # runtime + dump_to_writer (serde-gated)
        └── api-parity-rs-macros/      # #[parity], #[parity_impl]
```

## Origin / what was ported

Code was lifted (and renamed) from `../spark-connect` as of 2026-05-06,
then renamed again 2026-05-07 (`parity` → `api-parity`):

- `tools/pyspark_inventory.py` → `api-parity-py/src/api_parity_py/walk.py`
  (output flattened to `entries[]`, `kind` set per item).
- `crates/api-parity/src/lib.rs` → `api-parity-rs/crates/api-parity-rs/src/lib.rs`
  (field rename `reference` → `path`; added serde-gated `dump_to_writer`).
- `crates/api-parity-macros/src/lib.rs` → `api-parity-rs/crates/api-parity-rs-macros/src/lib.rs`
  (arg rename `reference` → `path`).
- `tools/parity_report.py` → `api-parity/src/api_parity/{compare,render_markdown,render_json}.py`
  (split into pure differ + renderer; consumes the new flat schema).

If you find behaviors that were in the originals but missing here,
that's almost certainly an oversight worth fixing — the originals are
still the closest thing to a reference implementation we have.
