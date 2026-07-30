"""Synthetic source file for the AST mode.

Each member is here to exercise one branch of the parse:
  - `run`: regular method
  - `label`: `@property` → detected by decorator spelling
  - `cached`: `@cached_property` → also a property
  - `build`: `@classmethod` → still a method
  - `wrapped`: decorator written as a call → must be unwrapped
  - `_hidden`: underscore-prefixed → must be skipped
  - `CONSTANT`: plain class attribute → not API surface
  - `Inner`: nested class → must be emitted with dotted qualname
  - `Derived`: subclass → inherited members must NOT appear on it
  - `helper`: module-level free function
"""

from functools import cached_property, lru_cache


class Gadget:
    CONSTANT = 42

    def run(self) -> int:
        return 1

    @property
    def label(self) -> str:
        return "gadget"

    @cached_property
    def cached(self) -> str:
        return "cached"

    @classmethod
    def build(cls) -> "Gadget":
        return cls()

    @lru_cache(maxsize=1)
    def wrapped(self) -> None:
        pass

    def _hidden(self) -> None:
        pass

    class Inner:
        def baz(self) -> None:
            pass


class Derived(Gadget):
    """Inherits `run`, but the parse cannot see across the base class."""

    def extra(self) -> None:
        pass


def helper() -> None:
    pass


def _private_helper() -> None:
    pass
