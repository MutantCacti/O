"""
Transformer base class - I/O substrate for O.

Transformers are the interface between O and external programs (humans, LLMs,
other O instances). They provide:
- read_command(): Non-blocking read from entity's input
- write_output(): Write execution results to entity's output
- ensure_entity_fifos(): Create I/O channels for an entity

Entity registry lives in Body.entity_spaces, NOT in transformers.
Transformers are purely I/O - they don't decide which entities exist.

The fundamental implementation is FifoManager - per-entity named pipes.
All other "transformers" are external programs that write to those FIFOs.

All transformers are async for safe concurrent I/O.
"""

from abc import ABC, abstractmethod
from typing import Optional


class Transformer(ABC):
    """
    Abstract I/O substrate for entity commands.

    Body polls entities (from body.entity_spaces) each tick, using
    transformers to read commands and write results.

    The transformer doesn't decide WHICH entities exist or WHAT they do -
    it just moves commands in and results out. Entity registry is Body's
    responsibility. Decision-making happens externally (in LLM agents,
    human terminals, etc.) which write to the I/O channels.
    """

    @abstractmethod
    async def read_command(self, entity: str) -> Optional[str]:
        """
        Non-blocking read from entity's input channel.

        Args:
            entity: Entity name (e.g., "@alice")

        Returns:
            Command string if available, None otherwise
        """
        pass

    @abstractmethod
    async def write_output(self, entity: str, output: dict) -> None:
        """
        Write execution result to entity's output channel.

        Args:
            entity: Entity name
            output: Result dict (implementation may add metadata)
        """
        pass

    def ensure_entity_fifos(self, entity: str) -> None:
        """
        Create I/O channels for an entity (optional).

        Not all transformers need this - e.g., in-memory test transformers
        don't have persistent channels to create.

        Args:
            entity: Entity name (e.g., "@alice")
        """
        pass  # Default: no-op
