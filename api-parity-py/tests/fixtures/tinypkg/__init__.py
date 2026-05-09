"""Synthetic test package — re-exports a class and a function from
submodules to verify the walker's "skip re-exports" rule."""

from .core import Widget
from .extras import helper

__all__ = ["Widget", "helper"]
