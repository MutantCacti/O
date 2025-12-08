"""
Human transformer - REFERENCE STUB for testing.

Implements the new transformer interface (list_entities, read_command, write_output)
with a simple in-memory buffer. For testing only.

Real human input should use FifoManager - humans write to FIFOs.
"""

from typing import Optional, List
from .base import Transformer


class HumanTransformer(Transformer):
    """
    REFERENCE STUB - for testing only.

    In-memory buffer that implements the transformer interface.
    Use submit() to queue a command, read_command() to retrieve it.

    Real human input should use FifoManager.
    """

    def __init__(self):
        self._pending = {}  # entity -> command
        self._outputs = {}  # entity -> list of outputs

    def list_entities(self) -> List[str]:
        """Return entities with pending commands."""
        return list(self._pending.keys())

    async def read_command(self, entity: str) -> Optional[str]:
        """
        Return pending command for entity, clearing it.

        Returns:
            Command string if pending, None otherwise
        """
        return self._pending.pop(entity, None)

    async def write_output(self, entity: str, output: dict) -> None:
        """Store output (for testing verification)."""
        if entity not in self._outputs:
            self._outputs[entity] = []
        self._outputs[entity].append(output)

    # Test helpers

    def submit(self, entity: str, command: str):
        """
        Submit command for entity (testing helper).

        Args:
            entity: Entity name
            command: Command string
        """
        self._pending[entity] = command

    def get_outputs(self, entity: str) -> List[dict]:
        """Get stored outputs for entity (testing helper)."""
        return self._outputs.get(entity, [])
