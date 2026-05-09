"""Core module of the synthetic test package.

Each member is here to exercise one branch of the walker:
  - `foo`: regular method
  - `bar`: property (must be detected via raw __dict__ lookup, not getattr)
  - `bake`: classmethod (callable, but the raw descriptor is a classmethod)
  - `_private`: underscore-prefixed → must be skipped
  - `Inner`: nested class → must be emitted with dotted qualname
  - `RowLike`: tuple subclass → must be filtered as a data shape
"""


class Widget:
    """Public widget."""

    CONSTANT = 42  # plain class attribute — not API surface, must be skipped

    def foo(self) -> int:
        return 1

    @property
    def bar(self) -> str:
        return "bar"

    @classmethod
    def bake(cls) -> "Widget":
        return cls()

    def _private(self) -> None:
        pass

    class Inner:
        """Nested class — its qualname is `Widget.Inner`."""

        def baz(self) -> None:
            pass


class RowLike(tuple):
    """tuple subclass — counted as a data shape, must be excluded."""
