# Contributing to api-parity

Most contributions land in one of three places:

- **`api-parity/`** — the language-agnostic differ + report renderer.
- **`api-parity-py/`** — Python plugin (reference + port).
- **`api-parity-rs/`** — Rust plugin (reference + port).

Adding a new language usually means writing a new plugin, not touching
the differ. This guide is for that case.

## Writing a plugin

A plugin is an executable named `api-parity-<lang>` that emits JSON
matching the schema in [`SCHEMA.md`](SCHEMA.md). Three things to decide
upfront:

1. **Which `kind`s do you support?** A `reference` envelope describes the
   canonical API surface ("these paths exist"). A `port` envelope
   describes the local implementation's claims ("we mirror these paths
   with this status"). A plugin can support one or both.
2. **Which `mode`s do you support?** A `walker` produces entries by
   inspecting a target's public API surface (introspection, AST parsing,
   rustdoc-json, etc.). An `annotation` mode collects markers attached
   directly to local code (Python decorators, Rust attribute macros).
   `kind` and `mode` are orthogonal — see *Modes* below.
3. **What is `path`?** The join key. Both sides of a comparison must
   agree on a dotted-name convention. Typically the reference's natural
   path (e.g. `pyspark.sql.session.SparkSession.sql`). Port entries
   echo that string verbatim; the local symbol goes in `implementation`.

### CLI contract

```
api-parity-<lang> <kind> [--mode walker|annotation] <target> [-o PATH | -]
```

- `kind`: `reference` or `port`.
- `--mode`: defaults to `walker` for `reference`, `annotation` for `port`.
  Override when you want the inverted shape.
- `target`: plugin-specific (a Python package name, a Rust crate path, …).
- `-o PATH`: output file, or `-` for stdout. Default stdout.
- Exit `64` with a stderr message when the requested `kind` or
  `(kind, mode)` combination isn't supported or isn't yet implemented.

### Wire format

Top-level envelope, plus per-kind entry shape: see
[`SCHEMA.md`](SCHEMA.md). Two rules worth highlighting:

- Reference entries are `{path, kind}` and nothing else — their truth is
  "this exists".
- Port entries carry `status`, `implementation`, optional `since`/`issue`/`comment`.
  `comment` is **required** when `status == unimplemented`.

### Stable output

Sort entries by `path` (and dedup on `(path, kind)` for references). The
JSON is part of the contract — version-to-version diffs should be minimal
noise.

### Modes

The two production modes are orthogonal to the two kinds:

|                       | `mode = walker`                                    | `mode = annotation`                                  |
| --------------------- | -------------------------------------------------- | ---------------------------------------------------- |
| `kind = reference`    | **Default.** Inspect a target's public API surface and emit `{path, kind}` per item. | Code-level declarations (e.g. `@reference(path=…)`) collected at import/link time. |
| `kind = port`         | Treat every walked item as `status = implemented`; `implementation` = the local symbol. Useful when both sides share a path scheme (e.g. rs-port vs rs-reference). | **Default.** Decorators / attribute macros (`@parity` / `#[parity]`) declare what the local code mirrors and at what status. |

A walker is whatever way the host language exposes its public API:
`inspect.getmembers` for Python, `cargo +nightly rustdoc --output-format
json` for Rust, etc. An annotation system is whatever attaches metadata
to code in that language: decorators, attribute macros, Java
annotations, TypeScript decorators, C# attributes.

Cross-language walker-as-port is technically allowed but practically
needs a path-scheme translation (Rust paths use `::`, Python paths use
`.`). The differ itself doesn't translate — provide a path rewrite at
the plugin level if you need it.

## Testing a plugin against the differ

```bash
api-parity-<lang> reference <target> -o ref.json
api-parity-<lang> port      <target> -o port.json
api-parity compare ref.json port.json
```

If your plugin is symmetric you can run it against itself; otherwise pair
it with another plugin (e.g. `api-parity-py reference pyspark` against
an `api-parity-rs port` of an annotated Rust crate).

## Repo conventions

- Each package versions independently. The two crates inside
  `api-parity-rs/` (`api-parity-rs` — lib + bin in one crate — and
  `api-parity-rs-macros`, kept separate because `proc-macro = true` crates
  can't ship anything else) move in lockstep — bump
  `[workspace.package].version` and the `=X.Y.Z` pin under
  `[workspace.dependencies]` together.
- Bump `schema_version` in `SCHEMA.md` (and gate readers on it) when the
  wire format changes; package versions are independent of this.
- Tests live under each package's `tests/` directory and run via the
  per-package CI job (`pytest tests` for Python, `cargo test --workspace
  --all-features` for Rust).

## Releasing

Releases are tag-driven. Push a tag matching one of:

- `vX.Y.Z`     (the differ; PyPI dist `api-parity`)
- `py-vX.Y.Z`  (the Python plugin)
- `rs-vX.Y.Z`  (the Rust plugin workspace)

The `Build / Test / Draft` workflow builds the artifacts and creates a
*draft* GitHub release. When the draft looks right, run the `Release`
workflow (`workflow_dispatch`) with the same tag — it promotes the draft
and publishes to PyPI (for the Python packages) or crates.io (for `rs`:
`api-parity-rs-macros` first, then `api-parity-rs`).

The `Makefile` has shortcuts: `make tag-core VERSION=0.0.2`,
`make tag-py VERSION=0.0.2`, `make tag-rs VERSION=0.0.2`.
