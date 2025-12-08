r"""
Echo interactor - simplest possible interactor for testing.

\echo Hello world ---
→ "Echo: Hello world"
"""

from grammar.parser import Command, Text
from interactors.base import Interactor


class EchoInteractor(Interactor):
    """
    Echoes back the command arguments.

    Used for:
    - Testing mind→body→interactor chain
    - Verifying command parsing
    - Base camp / sanity check
    """

    def execute(self, cmd: Command, executor: str = None) -> str:
        """
        Echo back the text content of the command.

        Args:
            cmd: Parsed command (cmd.name is "echo", cmd.content is arguments)
            executor: Who is executing (unused by echo)

        Returns:
            "Echo: <text content>"
        """
        # Extract all text nodes (command name already stripped by parser)
        text_parts = []
        for node in cmd.content:
            if isinstance(node, Text):
                content = node.text.strip()
                if content:
                    text_parts.append(content)

        message = " ".join(text_parts)
        return f"Echo: {message}"
