# api-parity wire format (schema v1)

Every plugin emits, and `api-parity` consumes, JSON in this shape.
Plugins must produce **one** of two `kind`s: `reference` or `port`.

## Envelope

```json
{
  "schema_version": 1,
  "kind": "reference",
  "language": "python",
  "version": "3.5.4",
  "source": "pyspark.sql.connect",
  "entries": [ ... ]
}
```

| Field            | Type     | Notes                                                                      |
| ---------------- | -------- | -------------------------------------------------------------------------- |
| `schema_version` | int      | Always `1` for now.                                                        |
| `kind`           | string   | `"reference"` or `"port"`.                                                 |
| `language`       | string   | `"python"`, `"rust"`, ... — informational only; `api-parity` ignores it. |
| `version`        | string   | The package's version (e.g. `pyspark.__version__`, `CARGO_PKG_VERSION`).   |
| `source`         | string   | What was scanned — package name for python, crate name for rust, etc.     |
| `entries`        | array    | See below.                                                                 |

## Reference entries

Reference entries describe the canonical public API surface — the set of
paths that "exist" on the side being mirrored.

```json
{"path": "pyspark.sql.session.SparkSession",         "kind": "class"}
{"path": "pyspark.sql.session.SparkSession.sql",     "kind": "method"}
{"path": "pyspark.sql.session.SparkSession.builder", "kind": "property"}
{"path": "pyspark.sql.functions.col",                "kind": "function"}
```

| Field  | Type   | Notes                                                       |
| ------ | ------ | ----------------------------------------------------------- |
| `path` | string | Canonical dotted name. Must be unique within the envelope.  |
| `kind` | string | One of: `class`, `method`, `property`, `function`.          |

Reference entries do not carry `comment` — their truth is "this exists".
A comment on the port side is what the report renders.

## Port entries

Port plugins describe what the local implementation claims to mirror.

```json
{
  "path": "pyspark.sql.session.SparkSession.sql",
  "implementation": "SparkSession::sql",
  "status": "implemented",
  "since": "3.4",
  "issue": null,
  "comment": null
}
```

| Field            | Type            | Notes                                                                      |
| ---------------- | --------------- | -------------------------------------------------------------------------- |
| `path`           | string          | Must match a reference `path` to count as covered.                         |
| `implementation` | string          | Local symbol path; a fn, method, or type (e.g. `SparkSession::sql`).       |
| `status`         | string          | `implemented`, `partial`, `unimplemented`.                                 |
| `since`          | string \| null  | Version where this became available, opaque to core.                       |
| `issue`          | int \| null     | Tracker issue number, opaque to core.                                      |
| `comment`        | string \| null  | Required when `status == unimplemented`; otherwise free-form.              |

## Joining

`api-parity` left-joins port entries onto reference entries by `path`.
A reference path with no port entry is **uncovered**. A port entry with
no reference path is **stale** (reference moved/renamed/typo).

## Plugin CLI contract

Every plugin must support:

```
api-parity-<name> <kind> [--mode walker|annotation] <target> [-o PATH | -]
  kind    one of: reference | port
  --mode  how entries are produced (defaults: reference→walker, port→annotation)
  target  plugin-specific (e.g. python package name, rust crate path)
  -o      output path, or `-` for stdout (default: stdout)
```

`kind` is the consumer-side concept (what role this envelope plays in the
diff). `mode` is the producer-side concept (how the plugin gathered the
entries — by *walking* the target's public API, by collecting *annotations*
attached to local code, or by *parsing* source without loading it). The wire
format above is identical across modes: the differ doesn't care how an
envelope was produced, only what it claims.

`target` names the same thing in every mode — the module, package, or crate
being inventoried. `walker` and `annotation` load it, so it must be
importable or buildable.

`--mode` selects among the modes that need nothing but a target. A mode
needing more is selected by the argument it requires: `ast` loads nothing,
so it has to be told where the source is, and `api-parity-py` spells that
`--from-source PATH`.

Not every plugin implements every mode; `ast` is available in `api-parity-py`
for `kind = reference` as of py-0.0.3.

A plugin exits 64 with a stderr message when the requested `kind` or
`(kind, mode)` combination isn't supported or isn't yet implemented.
