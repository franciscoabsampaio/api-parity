"""Annotated classes/functions used by the port + reference annotation tests."""

from api_parity_py import Status, parity, parity_impl, parity_ref


@parity_impl(path="ext.widget.Widget", status=Status.IMPLEMENTED, since="1.0")
class Widget:
    @parity(path=".foo", status=Status.IMPLEMENTED)
    def foo(self):
        return 1

    @parity(path=".bar", status=Status.PARTIAL, comment="missing batch mode")
    def bar(self):
        return 2

    @parity(
        path=".baz",
        status=Status.UNIMPLEMENTED,
        comment="todo",
        issue=42,
    )
    def baz(self):
        raise NotImplementedError


@parity_impl
class Naked:
    """No class-level entry; child uses an absolute path."""

    @parity(path="ext.naked.absolute_only", status=Status.IMPLEMENTED)
    def whatever(self):
        return 0


@parity(path="ext.free.solo", status=Status.PARTIAL, comment="wip")
def free_fn():
    return None


@parity_ref(path="ext.spec.Declared", kind="class")
class Declared:
    pass
