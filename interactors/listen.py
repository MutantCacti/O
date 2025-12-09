r"""
Listen interactor - subscribe to spaces for message delivery.

\listen @bob #general ---
→ Subscribes executor to messages from @bob and #general

When entity wakes, wake interactor fetches new messages from
listened spaces and appends them to the self_prompt.
"""

import json
from pathlib import Path
from grammar.parser import Command, Text, Entity, Space
from interactors.base import Interactor


class ListenInteractor(Interactor):
    r"""
    Subscribe to spaces for automatic message delivery on wake.

    Stores subscriptions in memory/listen/{entity}.json.
    Wake interactor reads these to bundle messages into self_prompt.
    """

    def __init__(self, body=None, memory_root="memory/listen"):
        """
        Create listen interactor.

        Args:
            body: Body instance
            memory_root: Where to store subscription files
        """
        self.body = body
        self.memory_root = Path(memory_root)
        self.memory_root.mkdir(parents=True, exist_ok=True)

    def _get_listen_file(self, entity: str) -> Path:
        """Get path to entity's listen file."""
        safe_name = entity.replace("@", "").replace("/", "_")
        return self.memory_root / f"{safe_name}.json"

    def _load_subscriptions(self, entity: str) -> list[str]:
        """Load subscriptions for entity."""
        path = self._get_listen_file(entity)
        if not path.exists():
            return []
        try:
            with open(path) as f:
                data = json.load(f)
                return data.get("spaces", [])
        except (json.JSONDecodeError, OSError):
            return []

    def _save_subscriptions(self, entity: str, spaces: list[str]):
        """Save subscriptions for entity."""
        path = self._get_listen_file(entity)
        with open(path, "w") as f:
            json.dump({"entity": entity, "spaces": spaces}, f, indent=2)

    def get_subscriptions(self, entity: str) -> list[str]:
        """
        Get subscribed spaces for entity.

        Public method for wake interactor to use.

        Args:
            entity: Entity to get subscriptions for

        Returns:
            List of space identifiers (e.g., ["@bob", "#general"])
        """
        return self._load_subscriptions(entity)

    def execute(self, cmd: Command, executor: str = None) -> str:
        """
        Subscribe to spaces.

        Args:
            cmd: Parsed command with entity/space targets
            executor: Entity subscribing

        Returns:
            Confirmation message
        """
        if not executor:
            return "ERROR: Listen requires executor context"

        # Extract targets (entities and spaces)
        targets = []
        for node in cmd.content:
            if isinstance(node, Entity):
                targets.append(f"@{node.name}")
            elif isinstance(node, Space):
                targets.append(f"#{node.name}")

        if not targets:
            return r"ERROR: No targets specified. Usage: \listen @entity #space ---"

        # Load existing and merge
        existing = set(self._load_subscriptions(executor))
        existing.update(targets)

        # Save
        self._save_subscriptions(executor, sorted(existing))

        # Update body.entity_spaces so incoming/read can find messages
        if self.body and hasattr(self.body, 'entity_spaces'):
            if executor not in self.body.entity_spaces:
                self.body.entity_spaces[executor] = set()
            for target in targets:
                # For entity targets, compute the entity-addressed space ID
                if target.startswith("@"):
                    members = sorted([executor, target])
                    space_id = "-".join(members)
                else:
                    # Named space uses target as-is
                    space_id = target
                self.body.entity_spaces[executor].add(space_id)

        return f"Listening to: {', '.join(sorted(existing))}"
