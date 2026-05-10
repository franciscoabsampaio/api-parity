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

## Things you'll want to do

In rough priority:

1. `git init` the repo, add a sensible `.gitignore` (Python: `*.egg-info`,
   `__pycache__`, `dist/`, `.venv`. Rust: `target/`, `Cargo.lock` for libs).
2. Migrate `spark-connect` (sibling repo at `../spark-connect`) off its
   in-tree `crates/api-parity-{core,macros}` and onto this repo's
   `api-parity-rs` + `api-parity-rs-macros`. The macros there use
   the arg name `reference = "..."` while these use `path = "..."` —
   that's the one breaking rename. The emitted code targets
   `::api_parity_rs::...` instead of `::api_parity::...`
   (note the `_rs_` infix).
3. Decide how `api-parity-rs` is consumed: a published crates.io
   release, a git dep, or a path dep. `api-parity-{core,py}` same
   question for PyPI.
4. Tests:
   - `api-parity-rs`: copy the 6 tests in
     `../spark-connect/crates/api-parity/tests/macros.rs`, rename
     the inner crate paths from `api_parity` → `api_parity_rs`,
     and rename `reference =` → `path =`.
   - `api-parity-py`: a couple of golden-file tests against a tiny
     synthetic package would be more useful than tests against pyspark
     itself.
   - `api-parity`: feed it two hand-written JSON envelopes and
     assert on the rendered Markdown.
5. Per-language plugin guide: a short `CONTRIBUTING.md` describing how
   to write a new plugin (just the JSON contract + CLI shape).

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
