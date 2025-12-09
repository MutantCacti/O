r"""
Incoming interactor - check for unread messages.

\incoming ---
→ "true" if executor has unread messages, "false" otherwise

Used with \wake to wake when messages arrive:
\wake $(\incoming---) Check my messages ---
"""

import json
from pathlib import Path
from grammar.parser import Command
from interactors.base import Interactor


class IncomingInteractor(Interactor):
    r"""
    Check if executor has unread messages.

    Scans space files in memory/spaces/ for messages addressed to executor.
    Tracks last-seen message count per entity in memory/incoming/.

    Returns "true" if new messages since last check, "false" otherwise.
    """

    def __init__(self, body=None, spaces_root="memory/spaces", state_root="memory/incoming"):
        """
        Create incoming interactor.

        Args:
            body: Body instance (for entity context)
            spaces_root: Where space message files live
            state_root: Where to track read state per entity
        """
        self.body = body
        self.spaces_root = Path(spaces_root)
        self.state_root = Path(state_root)
        self.state_root.mkdir(parents=True, exist_ok=True)

    def _get_state_file(self, entity: str) -> Path:
        """Get path to entity's incoming state file."""
        safe_name = entity.replace("@", "").replace("/", "_")
        return self.state_root / f"{safe_name}.json"

    def _load_state(self, entity: str) -> dict:
        """Load read state for entity."""
        path = self._get_state_file(entity)
        if not path.exists():
            return {}
        try:
            with open(path) as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return {}

    def _save_state(self, entity: str, state: dict):
        """Save read state for entity."""
        path = self._get_state_file(entity)
        with open(path, "w") as f:
            json.dump(state, f)

    def _find_entity_spaces(self, entity: str) -> list[Path]:
        """Find all space files for entity from body.entity_spaces."""
        if not self.body or not hasattr(self.body, 'entity_spaces'):
            return []

        spaces = self.body.entity_spaces.get(entity, set())
        if not spaces:
            return []

        return [self.spaces_root / f"{space_id}.jsonl" for space_id in spaces]

    def _count_messages(self, space_file: Path) -> int:
        """Count messages in a space file."""
        if not space_file.exists():
            return 0
        try:
            with open(space_file) as f:
                return sum(1 for line in f if line.strip())
        except OSError:
            return 0

    def execute(self, cmd: Command, executor: str = None) -> str:
        """
        Check for incoming messages.

        Args:
            cmd: Parsed command (no arguments needed)
            executor: Entity to check messages for

        Returns:
            "true" if new messages, "false" otherwise
        """
        if not executor:
            return "ERROR: Incoming requires executor context"

        # Find spaces this entity is part of
        spaces = self._find_entity_spaces(executor)

        if not spaces:
            return "false"

        # Load previous state
        state = self._load_state(executor)

        # Check each space for new messages
        has_new = False
        new_state = {}

        for space_file in spaces:
            space_name = space_file.stem
            current_count = self._count_messages(space_file)
            previous_count = state.get(space_name, 0)

            new_state[space_name] = current_count

            if current_count > previous_count:
                has_new = True

        # Save new state
        self._save_state(executor, new_state)

        return "true" if has_new else "false"
