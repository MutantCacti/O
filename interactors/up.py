r"""
Up interactor - always returns true.

\up ---
→ "true"

Used with \wake for single wake cycle:
\wake $(\up---) Process next message ---
"""

from grammar.parser import Command
from interactors.base import Interactor


class UpInteractor(Interactor):
    r"""
    Always returns true.

    Simplest wake condition - entity wakes once.
    To stay active, entity must call \wake again after processing.
    """

    def execute(self, cmd: Command, executor: str = None) -> str:
        return "true"
