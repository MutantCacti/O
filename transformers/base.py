"""
Transformer base class - I/O substrate for O.

Transformers are the interface between O and external programs (humans, LLMs,
other O instances). They provide:
- list_entities(): Which entities have I/O channels
- read_command(): Non-blocking read from entity's input
- write_output(): Write execution results to entity's output

The fundamental implementation is FifoManager - per-entity named pipes.
All other "transformers" are external programs that write to those FIFOs.

All transformers are async for safe concurrent I/O.
"""

from abc import ABC, abstractmethod
from typing import Optional, List


class Transformer(ABC):
    """
    Abstract I/O substrate for entity commands.

    Body polls transformers each tick to read commands from entities.
    Commands are executed through Mind, results written back.

    The transformer doesn't decide WHAT entities do - it just moves
    commands in and results out. Decision-making happens externally
    (in LLM agents, human terminals, etc.) which write to the I/O channels.
    """

    @abstractmethod
    def list_entities(self) -> List[str]:
        """
        List all entities with I/O channels.

        Returns:
            List of entity names (e.g., ["@alice", "@bob"])
        """
        pass

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
