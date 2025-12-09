"""
mind.py - The execution engine

Takes command strings, parses them, executes them.
That's it.
"""

import asyncio
from grammar.parser import parse, Command


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

    async def execute(self, command_str: str, executor: str = None) -> str:
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

            # Find interactor by command name (provided by parser)
            if cmd.name not in self.interactors:
                return f"ERROR: Unknown command '{cmd.name}'"

            # Execute (pass executor context)
            interactor = self.interactors[cmd.name]

            # Prefer execute_async if available (for async interactors like eval)
            if hasattr(interactor, 'execute_async'):
                return await interactor.execute_async(cmd, executor=executor)

            result = interactor.execute(cmd, executor=executor)

            # Support both sync and async interactors
            if asyncio.iscoroutine(result):
                return await result
            return result

        except Exception as e:
            return f"ERROR: {e}"
