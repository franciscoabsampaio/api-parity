# api-parity-py

Python plugin for the [`api-parity`](https://github.com/franciscoabsampaio/api-parity) project. Produces JSON envelopes that the [`api-parity`](https://pypi.org/project/api-parity/) differ consumes.

See the [project README](https://github.com/franciscoabsampaio/api-parity) for the full cross-language story (Python ↔ Rust, four directions).

## Install

```bash
pip install api-parity-py
```

## Modes

How entries get produced, chosen with `--mode`:

- **Walker** — introspects a package's public API via `inspect.getmembers` and emits one entry per class / method / property / function. Works on both kinds of envelope.
- **Annotation** — collects decorators (`@parity`, `@parity_impl`, `@parity_ref`) attached to your own code at import time. Works on both kinds of envelope.
- **AST** — parses source files with `ast`, without importing them. `reference` only.

Defaults: `reference → walker`, `port → annotation`.

## Usage

```bash
# Walk an upstream package as a reference:
api-parity-py reference pyspark.sql.connect -o ref.json

# Annotate your own port (see below) and dump it:
api-parity-py port mylib -o port.json

# Or walk your own library and treat every public API as implemented:
api-parity-py port --mode=walker mylib -o port.json
```

## Inventorying source you can't import

Both the walker and the annotation collector load the target. When that isn't possible — a test suite its distribution doesn't ship, or a module whose import pulls in a dependency graph that fails for reasons unrelated to the names you want — read the names off the syntax tree instead:

```bash
api-parity-py reference pyspark.sql.tests.test_catalog \
  --from-source vendor/test_catalog.py -o ref.json
```

`target` is the dotted name in every mode; `--from-source` (which selects `mode = ast`) only changes where the names are read from. Point it at a file and `target` names that module; point it at a directory and `target` names that package, with the files beneath it extending the name. Either way entries key to the paths your annotations are written against, not to where the source sits in your checkout.

Only lexically-present names are visible: base classes are names rather than resolved classes, so inherited members stay attributed to the class that declares them; import-time construction is invisible; and `kind` follows decorator spelling. Prefer the walker whenever the target imports cleanly.

## Annotating a Python port

```python
from api_parity_py import parity, parity_impl, Status

@parity_impl(path="pyspark.sql.session.SparkSession", status=Status.IMPLEMENTED)
class SparkSession:
    @parity(path=".sql", status=Status.IMPLEMENTED, since="3.4")
    def sql(self, query): ...

    @parity(path=".stop", status=Status.UNIMPLEMENTED, comment="no shutdown hook yet")
    def stop(self): ...
```

A leading `.` in a child `path` is rewritten to `<parent>.<child>` at decoration time. `Status.UNIMPLEMENTED` requires a `comment`.

For declarative reference inventories (rare — usually a walker is better), see `@parity_ref`.

## End-to-end

```bash
api-parity-py reference pyspark.sql.connect -o ref.json
api-parity-py port      mylib                -o port.json
api-parity   compare    ref.json port.json
```
