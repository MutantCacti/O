"""
Human transformer - REFERENCE STUB.

This is a temporary implementation for testing. It does NOT follow the
stateless transformer interface (think()) because human input requires
a different model: humans submit commands when ready, not on demand.

TODO: Replace with proper human input handling in v0.2.
"""

from typing import Optional, Dict, Any
from .base import Transformer


class HumanTransformer(Transformer):
    """
    REFERENCE STUB - for testing only.

    Does not implement the stateless think() interface properly.
    Humans submit input asynchronously via submit(), not on-demand.

    Will be replaced with proper human input handling.
    """

    def __init__(self):
        self.pending_input = None  # (entity, command) buffer

    async def think(self, entity: str, context: Dict[str, Any]) -> Optional[str]:
        """
        STUB: Returns pending input if entity matches, else None.

        This is not how human input should work - it's just for testing.
        Real human input needs an async queue per entity.
        """
        if self.pending_input and self.pending_input[0] == entity:
            _, command = self.pending_input
            self.pending_input = None
            return command
        return None

    def submit(self, entity: str, command: str):
        """
        Submit command for testing.

        Args:
            entity: Entity submitting command
            command: Command string
        """
        self.pending_input = (entity, command)
