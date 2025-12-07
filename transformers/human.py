"""
Human transformer - stdin/HTTP input device.

Polls for human input from stdin or HTTP endpoint.
No scheduling needed - humans type when ready.
"""

from typing import Optional, Tuple
from .base import Transformer


class HumanTransformer(Transformer):
    """
    Human input device.

    Simple polling - check if human has typed a command.
    No wake conditions, no scheduling - just direct input.
    """

    def __init__(self, input_source="stdin"):
        """
        Initialize human transformer.

        Args:
            input_source: "stdin" or "http" (future: HTTP endpoint)
        """
        self.input_source = input_source
        self.pending_input = None  # Buffer for testing

    def poll(self, body) -> Optional[Tuple[str, str]]:
        """
        Poll for human input.

        For now: Check pending_input buffer (for testing)
        Future: Check stdin or HTTP endpoint

        Returns:
            (entity, command) if input available, None otherwise
        """
        if self.pending_input:
            result = self.pending_input
            self.pending_input = None
            return result

        return None

    def submit(self, entity: str, command: str):
        """
        Submit command for next poll (testing helper).

        Args:
            entity: Entity submitting command
            command: Command string
        """
        self.pending_input = (entity, command)
