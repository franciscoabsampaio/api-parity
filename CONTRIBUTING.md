# Contributing to api-parity

Most contributions land in one of three places:

- **`api-parity/`** — the language-agnostic differ + report renderer.
- **`api-parity-py/`** — the Python reference plugin.
- **`api-parity-rs/`** — the Rust port plugin.

Adding a new language usually means writing a new plugin, not touching
core. This guide is for that case.

## Writing a plugin

A plugin is a single executable named `api-parity-<lang>` that emits JSON
matching the schema in [`SCHEMA.md`](SCHEMA.md). Two things to decide
upfront:

1. **Which `kind`?** A `reference` plugin walks a canonical API and emits
   the surface (every public class, method, property, function). A `port`
   plugin walks a local implementation and emits what it claims to mirror,
   tagged with `status` and `implementation`. Plugins can support one or
   both.
2. **What is `path`?** The join key. Both sides must agree on the same
   dotted-name convention — typically the reference language's natural
   path (e.g. `pyspark.sql.session.SparkSession.sql`). Port plugins
   echo that string verbatim; their own `implementation` field is what
   carries the local symbol path.

### CLI contract

```
api-parity-<lang> <kind> <target> [-o PATH | -]
```

- `kind`: one of `reference` or `port`.
- `target`: plugin-specific (e.g. a Python package name, a Rust crate path).
- `-o PATH`: output file, or `-` for stdout. Default stdout.
- Exit `64` with a stderr message when the requested `kind` isn't supported
  or isn't yet implemented.

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

### Implementation patterns

The user-facing CLI is the same shape for every plugin, but the language
dictates how you implement it:

- **Introspection** (`api-parity-py`): the plugin is a self-contained CLI
  that imports the target at runtime and walks it. Works wherever the host
  language has a usable reflection API.
- **Embedded dump** (`api-parity-rs`): the target depends on plugin
  libraries that record entries at compile/link time, and ships a tiny
  bin (`api-parity-dump`) that flushes them as JSON. The plugin's CLI is
  a wrapper that drives `cargo run --bin api-parity-dump --manifest-path
  <target>` (or the equivalent build invocation). Necessary for compiled
  languages where annotations exist only inside the target's compilation
  unit.

Both produce the same envelope and obey the same CLI contract.

## Testing a plugin against core

```bash
api-parity-<lang> reference <pkg> -o ref.json
api-parity-<lang> port      <pkg> -o port.json
api-parity compare ref.json port.json
```

If your plugin is symmetric you can run it against itself; otherwise pair
it with another plugin (e.g. `api-parity-py reference pyspark` →
`api-parity-rs`-built port from a target crate).

## Repo conventions

- Each package versions independently. The three crates inside
  `api-parity-rs/` (`-core`, `-macros`, the `-cli` published as
  `api-parity-rs`) move in lockstep — bump `[workspace.package].version`
  and the `=X.Y.Z` pin under `[workspace.dependencies]` together.
- Bump `schema_version` in `SCHEMA.md` (and gate readers on it) when the
  wire format changes; package versions are independent of this.
- Tests live under each package's `tests/` directory and run via the
  per-package CI job (`pytest tests` for Python, `cargo test --workspace
  --all-features` for Rust).

## Releasing

Releases are tag-driven. Push a tag matching one of:

- `api-parity-vX.Y.Z`     (the differ; PyPI dist `api-parity`)
- `api-parity-py-vX.Y.Z`  (the Python reference plugin)
- `api-parity-rs-vX.Y.Z`  (the Rust port plugin workspace)

The `Build / Test / Draft` workflow builds the artifacts and creates a
*draft* GitHub release. When the draft looks right, run the `Release`
workflow (`workflow_dispatch`) with the same tag — it promotes the draft
and publishes to PyPI (for the Python packages) or crates.io (for `rs`:
`api-parity-rs-macros` first, then `api-parity-rs-core`, then the
`api-parity-rs` CLI crate).
