"""ARIA — Adaptive Real-time Intelligent Assistant."""

from .cache import ResponseCache
from .voice_io import speak, listen
from .commands import CommandRegistry, build_registry

__all__ = ["ResponseCache", "speak", "listen", "CommandRegistry", "build_registry"]
__version__ = "2.0.0"
