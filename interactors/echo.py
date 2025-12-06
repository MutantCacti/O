"""
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
            cmd: Parsed command tree
            executor: Who is executing (unused by echo)

        Returns:
            "Echo: <text content>"
        """
        # Extract all text nodes, skip command name
        text_parts = []
        first = True
        for node in cmd.content:
            if isinstance(node, Text):
                content = node.text.strip()
                if first:
                    # First text node contains "echo ..." - strip "echo"
                    content = content.split(maxsplit=1)
                    if len(content) > 1:
                        text_parts.append(content[1])
                    first = False
                elif content:
                    text_parts.append(content)

        message = " ".join(text_parts)
        return f"Echo: {message}"
