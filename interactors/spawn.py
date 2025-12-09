r"""
Spawn interactor - create entities.

\spawn @alice ---
→ Creates entity @alice, sets up FIFOs

\spawn @(alice, bob) ---
→ Creates multiple entities
"""

from grammar.parser import Command, Text, Entity
from interactors.base import Interactor


class SpawnInteractor(Interactor):
    r"""
    Create entities in the environment.

    \spawn @alice ---
    → Registers @alice in body.entity_spaces
    → Creates FIFOs via transformer.ensure_entity_fifos()

    Requires body reference with transformer attached.
    """

    def __init__(self, body=None):
        self.body = body

    def execute(self, cmd: Command, executor: str = None) -> str:
        if not self.body:
            return "ERROR: Spawn requires body context"

        # Extract entity targets
        entities = []
        for node in cmd.content:
            if isinstance(node, Entity):
                entities.append(f"@{node.name}")

        if not entities:
            return r"ERROR: No entity specified. Usage: \spawn @entity ---"

        created = []
        errors = []

        for entity in entities:
            # Check if already exists
            if entity in self.body.entity_spaces:
                errors.append(f"{entity} already exists")
                continue

            # Register in spatial substrate
            self.body.entity_spaces[entity] = set()

            # Create FIFOs if transformer supports it
            if self.body.transformer and hasattr(self.body.transformer, 'ensure_entity_fifos'):
                try:
                    self.body.transformer.ensure_entity_fifos(entity)
                except Exception as e:
                    errors.append(f"{entity} FIFO creation failed: {e}")
                    continue

            created.append(entity)

        # Build response
        parts = []
        if created:
            parts.append(f"Spawned: {', '.join(created)}")
        if errors:
            parts.append(f"Errors: {'; '.join(errors)}")

        return " | ".join(parts) if parts else "No entities processed"
