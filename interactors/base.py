"""
Base interactor interface.

All interactors inherit from this.
"""

from abc import ABC, abstractmethod
from grammar.parser import Command


class Interactor(ABC):
    """
    Base class for all interactors (syscalls).

    Interactors receive parsed Command trees and return output strings.
    """

    @abstractmethod
    def execute(self, cmd: Command) -> str:
        """
        Execute command, return output.

        Args:
            cmd: Parsed Command tree

        Returns:
            Output string
        """
        raise NotImplementedError
