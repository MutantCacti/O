"""
mind.py - The execution engine

Takes command strings, parses them, executes them.
That's it.
"""

from grammar.parser import parse, Command, Text


class Mind:
    """
    The execution engine.

    Parse → Execute → Return output

    State/logs are external observers.
    """

    def __init__(self, interactors: dict):
        """
        Create mind with interactors.

        Args:
            interactors: {"say": SayInteractor(), ...}
        """
        self.interactors = interactors

    def execute(self, command_str: str, executor: str = None) -> str:
        """
        Execute a command, return output.

        Args:
            command_str: e.g. "\\say #general Hello ---"
            executor: Who is executing (entity name, e.g. "@alice")

        Returns:
            Output string
        """
        try:
            # Parse
            cmd = parse(command_str)

            # Find interactor
            command_name = self._get_command_name(cmd)

            if command_name not in self.interactors:
                return f"ERROR: Unknown command '{command_name}'"

            # Execute (pass executor context)
            interactor = self.interactors[command_name]
            return interactor.execute(cmd, executor=executor)

        except Exception as e:
            return f"ERROR: {e}"

    def _get_command_name(self, cmd: Command) -> str:
        """
        Extract command name from first Text node.

        Handles:
        - \\say hello --- (first node is Text)
        - \\say @alice hello --- (first node is Entity, need to find Text)
        """
        for node in cmd.content:
            if isinstance(node, Text):
                content = node.text.strip()
                if content:
                    # Get first word
                    return content.split()[0]
        return ""
