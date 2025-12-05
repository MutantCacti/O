"""
Base interactor interface.

All interactors inherit from this.
"""

from abc import ABC, abstractmethod
from grammar.parser import Command


class Interactor(ABC):
    """
    Base class for all interactors (syscalls).

    Interactors receive parsed Command trees and executor context,
    then return output strings.
    """

    @abstractmethod
    def execute(self, cmd: Command, executor: str = None) -> str:
        """
        Execute command, return output.

        Args:
            cmd: Parsed Command tree
            executor: Who is executing (entity name, e.g. "@alice")

        Returns:
            Output string
        """
        raise NotImplementedError
