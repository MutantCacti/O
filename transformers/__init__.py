"""
Transformers - I/O devices that Body polls for entity commands.

Transformers are external to O - they are users (human, LLM instances)
that Body polls for input. Body.tick() checks each transformer device
for commands and executes them.
"""

from .base import Transformer

__all__ = ["Transformer"]
