"""
Transformer base class - I/O devices for O.

Transformers are external agents (humans, LLMs) that Body polls for input.
They are NOT part of the O system - they are users of it, like devices.

Body.tick() polls transformers to get commands, then executes those commands
through Mind → Interactors → State.
"""

from abc import ABC, abstractmethod
from typing import Optional, Tuple


class Transformer(ABC):
    """
    Abstract I/O device that Body polls for entity commands.

    Different transformer types:
    - HumanTransformer: Polls stdin/HTTP for human input
    - AnthropicTransformer: Polls wake conditions, calls Claude API
    - DeepSeekTransformer: Polls wake conditions, calls DeepSeek API

    Body doesn't care about the difference - it just polls and executes.
    """

    @abstractmethod
    def poll(self, body) -> Optional[Tuple[str, str]]:
        """
        Poll this device for input.

        Args:
            body: Body instance (provides context - spaces, state, etc.)

        Returns:
            (entity, command_string) if input is ready
            None if no input available

        Example:
            ("@alice", "\\say #general Hello everyone! ---")
        """
        pass
