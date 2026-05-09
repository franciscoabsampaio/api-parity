"""Extras module — exists to verify free-function emission and the
underscore-skip rule for module-level callables."""


def helper(x: int) -> int:
    return x


def _hidden() -> None:
    """Underscore-prefixed → must be skipped."""
