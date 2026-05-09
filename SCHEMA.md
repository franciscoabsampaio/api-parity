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

Reference plugins describe the public API surface they walked.

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
| `implementation` | string          | Local symbol path (e.g. `SparkSession::sql`).                              |
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
api-parity-<name> <kind> <target> [-o PATH | -]
  kind    one of: reference | port
  target  plugin-specific (e.g. python package name, rust crate path)
  -o      output path, or `-` for stdout (default: stdout)
```

A plugin that does not support a `kind` exits 64 with a message on stderr.
