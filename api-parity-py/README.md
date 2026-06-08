# api-parity-py

Python plugin for the [`api-parity`](https://github.com/franciscoabsampaio/api-parity) project. Produces JSON envelopes that the [`api-parity`](https://pypi.org/project/api-parity/) differ consumes.

See the [project README](https://github.com/franciscoabsampaio/api-parity) for the full cross-language story (Python ↔ Rust, four directions).

## Install

```bash
pip install api-parity-py
```

## Two modes

The plugin supports both production modes on both kinds of envelope:

- **Walker** — introspects a package's public API via `inspect.getmembers` and emits one entry per class / method / property / function.
- **Annotation** — collects decorators (`@parity`, `@parity_impl`, `@parity_ref`) attached to your own code at import time.

Defaults: `reference → walker`, `port → annotation`. Override with `--mode`.

## Usage

```bash
# Walk an upstream package as a reference:
api-parity-py reference pyspark.sql.connect -o ref.json

# Annotate your own port (see below) and dump it:
api-parity-py port mylib -o port.json

# Or walk your own library and treat every public API as implemented:
api-parity-py port --mode=walker mylib -o port.json
```

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
