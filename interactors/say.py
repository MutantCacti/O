r"""
Say interactor - entity communication.

\say @bob Hello! ---
\say @(alice, bob) Hello both! ---
\say #general Hello everyone! ---
\say #(general, dev) Broadcast! ---

Entity targets: space ID derived from sorted entity set.
Space targets: looked up in body.spaces, must be member to send.
"""

from grammar.parser import Command, Text, Entity, Space
from interactors.base import Interactor
from pathlib import Path
import json
from datetime import datetime, UTC


class SayInteractor(Interactor):
    r"""
    Send message to spaces.

    \say @bob → entity-addressed space {executor, bob}
    \say #general → named space (must be member)
    \say #(general, dev) → broadcast to multiple named spaces

    TODO: @me resolution should happen somewhere (kernel interactor?)
          For now, @me is not resolved - use explicit entity names.
    """

    def __init__(self, body=None, spaces_root="memory/spaces"):
        self.body = body
        self.spaces_root = Path(spaces_root)
        self.spaces_root.mkdir(parents=True, exist_ok=True)

    def execute(self, cmd: Command, executor: str = None) -> str:
        if not executor:
            return "ERROR: Say requires executor context"

        # Extract targets (entities and spaces) and message content
        entity_targets = []
        space_targets = []
        message_parts = []

        for node in cmd.content:
            if isinstance(node, Entity):
                entity_targets.append(f"@{node.name}")
            elif isinstance(node, Space):
                space_targets.append(f"#{node.name}")
            elif isinstance(node, Text):
                text = node.text.strip()
                # Skip "say" command name
                if text.lower().startswith("say"):
                    text = text[3:].lstrip()
                if text:
                    message_parts.append(text)

        if not entity_targets and not space_targets:
            return "ERROR: No target specified. Usage: \\say @entity|#space message ---"

        message = " ".join(message_parts).strip()
        if not message:
            return "ERROR: No message content. Usage: \\say @entity|#space message ---"

        # Get tick
        tick = self.body.state.tick if (self.body and hasattr(self.body, 'state')) else 0

        # Create message entry
        entry = {
            "tick": tick,
            "sender": executor,
            "content": message,
            "timestamp": datetime.now(UTC).isoformat()
        }

        # Collect all spaces to write to
        destinations = []

        # Entity-addressed space (executor + targets)
        # NOTE: Does not register in body.spaces - file-only for now.
        #       Named spaces use body.spaces, entity-addressed don't.
        #       Revisit when building \hear/reading mechanism.
        if entity_targets:
            members = sorted(set([executor] + entity_targets))
            space_id = "-".join(members)
            destinations.append(space_id)

        # Named spaces (must be member)
        for space_name in space_targets:
            # Check space exists and executor is member
            if self.body and hasattr(self.body, 'spaces'):
                if space_name not in self.body.spaces:
                    return f"ERROR: Space {space_name} does not exist"
                if executor not in self.body.spaces[space_name].members:
                    return f"ERROR: Not a member of {space_name}"
            destinations.append(space_name)

        # Write to all destination spaces
        for dest in destinations:
            space_file = self.spaces_root / f"{dest}.jsonl"
            try:
                with open(space_file, "a") as f:
                    f.write(json.dumps(entry) + "\n")
            except (IOError, OSError) as e:
                return f"ERROR: Failed to write to {dest}: {e}"

        if len(destinations) == 1:
            return f"Sent to {destinations[0]}"
        else:
            return f"Sent to {', '.join(destinations)}"
