r"""
Read interactor - fetch messages from spaces.

\read ---              → All unread messages from all listened spaces
\read @bob ---         → Unread messages from @bob
\read #general ---     → Unread messages from #general

Returns formatted messages or "No new messages" if none.

Complements \incoming (which just returns true/false):
- \incoming → "do I have messages?" → true/false
- \read → "what are the messages?" → actual content
"""

import json
from pathlib import Path
from grammar.parser import Command, Text, Entity, Space
from interactors.base import Interactor


class ReadInteractor(Interactor):
    r"""
    Fetch and display messages from spaces.

    \read --- returns all unread messages from spaces the executor
    is a member of. Optionally filter by target (@entity or #space).

    Tracks read state per entity so messages aren't repeated.
    """

    def __init__(self, body=None, spaces_root="memory/spaces", state_root="memory/read"):
        """
        Create read interactor.

        Args:
            body: Body instance (for entity_spaces lookup)
            spaces_root: Where space message files live
            state_root: Where to track read state per entity
        """
        self.body = body
        self.spaces_root = Path(spaces_root)
        self.state_root = Path(state_root)
        self.state_root.mkdir(parents=True, exist_ok=True)

    def _get_state_file(self, entity: str) -> Path:
        """Get path to entity's read state file."""
        safe_name = entity.replace("@", "").replace("/", "_")
        return self.state_root / f"{safe_name}.json"

    def _load_state(self, entity: str) -> dict:
        """Load read state for entity. Returns {space_id: last_read_index}."""
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

    def _get_space_file(self, space_id: str) -> Path:
        """Get path to space message file."""
        return self.spaces_root / f"{space_id}.jsonl"

    def _read_messages(self, space_file: Path, start_index: int = 0) -> list[dict]:
        """Read messages from space file starting at index."""
        if not space_file.exists():
            return []
        try:
            with open(space_file) as f:
                lines = f.readlines()
            messages = []
            for i, line in enumerate(lines):
                if i < start_index:
                    continue
                line = line.strip()
                if line:
                    try:
                        msg = json.loads(line)
                        msg["_index"] = i
                        messages.append(msg)
                    except json.JSONDecodeError:
                        pass
            return messages
        except OSError:
            return []

    def _count_messages(self, space_file: Path) -> int:
        """Count total messages in space file."""
        if not space_file.exists():
            return 0
        try:
            with open(space_file) as f:
                return sum(1 for line in f if line.strip())
        except OSError:
            return 0

    def _find_entity_spaces(self, entity: str) -> set[str]:
        """Find all spaces entity is a member of."""
        if not self.body or not hasattr(self.body, 'entity_spaces'):
            return set()
        return self.body.entity_spaces.get(entity, set())

    def _resolve_space_id(self, executor: str, target: str) -> str | None:
        """
        Resolve target to space ID.

        @bob → sorted entity pair space (@alice-@bob)
        #general → #general
        """
        if target.startswith("@"):
            # Entity-addressed space
            members = sorted([executor, target])
            return "-".join(members)
        elif target.startswith("#"):
            # Named space
            return target
        return None

    def execute(self, cmd: Command, executor: str = None) -> str:
        """
        Read messages from spaces.

        Args:
            cmd: Parsed command, optionally with @entity or #space targets
            executor: Entity reading messages

        Returns:
            Formatted messages or "No new messages"
        """
        if not executor:
            return "ERROR: Read requires executor context"

        # Extract filter targets
        targets = []
        for node in cmd.content:
            if isinstance(node, Entity):
                targets.append(f"@{node.name}")
            elif isinstance(node, Space):
                targets.append(f"#{node.name}")

        # Determine which spaces to read from
        if targets:
            # Filter to specific targets
            space_ids = set()
            for target in targets:
                space_id = self._resolve_space_id(executor, target)
                if space_id:
                    space_ids.add(space_id)
        else:
            # All spaces executor is a member of
            space_ids = self._find_entity_spaces(executor)

        if not space_ids:
            return "No subscribed spaces"

        # Load read state
        state = self._load_state(executor)

        # Collect unread messages from all spaces
        all_messages = []
        new_state = dict(state)

        for space_id in space_ids:
            space_file = self._get_space_file(space_id)
            last_read = state.get(space_id, 0)

            messages = self._read_messages(space_file, start_index=last_read)
            for msg in messages:
                msg["_space"] = space_id
                all_messages.append(msg)

            # Update state to mark all as read
            total = self._count_messages(space_file)
            new_state[space_id] = total

        # Save new state
        self._save_state(executor, new_state)

        if not all_messages:
            return "No new messages"

        # Format output
        lines = []
        for msg in all_messages:
            sender = msg.get("sender", "?")
            content = msg.get("content", "")
            space = msg.get("_space", "")
            lines.append(f"[{space}] {sender}: {content}")

        return "\n".join(lines)
