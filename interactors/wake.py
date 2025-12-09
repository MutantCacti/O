r"""
Wake interactor - Register and check wake conditions.

\wake ?($(\up---)) My self-prompt ---
\wake ?($(\incoming---) or $(\tick---) > 100) Check messages ---
→ Registers condition, returns confirmation

Transformer checks wake.should_wake(entity) to determine if entity should think.
When condition evaluates to true, entity wakes with self_prompt + messages
from listened spaces (see \listen interactor).

Wake records are stored in memory/wake/{entity}.json
"""

import json
from pathlib import Path
from grammar.parser import (
    Command, Text, Condition, ConditionExpr,
    BoolOr, BoolAnd, BoolNot, Compare,
    SchedulerQuery, Entity, Space,
)
from interactors.base import Interactor
from interactors.eval import evaluate_condition
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from interactors.listen import ListenInteractor


def _serialize_condition(expr: ConditionExpr) -> dict:
    """Serialize a condition expression tree to JSON-compatible dict."""
    if isinstance(expr, BoolOr):
        return {"type": "or", "left": _serialize_condition(expr.left), "right": _serialize_condition(expr.right)}
    elif isinstance(expr, BoolAnd):
        return {"type": "and", "left": _serialize_condition(expr.left), "right": _serialize_condition(expr.right)}
    elif isinstance(expr, BoolNot):
        return {"type": "not", "operand": _serialize_condition(expr.operand)}
    elif isinstance(expr, Compare):
        return {"type": "compare", "op": expr.op, "left": _serialize_condition(expr.left), "right": _serialize_condition(expr.right)}
    elif isinstance(expr, SchedulerQuery):
        # Serialize the command nodes
        return {"type": "query", "command": [_serialize_node(n) for n in expr.command]}
    elif isinstance(expr, Text):
        return {"type": "text", "value": expr.text}
    elif isinstance(expr, Entity):
        return {"type": "entity", "name": expr.name}
    elif isinstance(expr, Space):
        return {"type": "space", "name": expr.name}
    else:
        return {"type": "unknown"}


def _serialize_node(node) -> dict:
    """Serialize a parser node."""
    if isinstance(node, Text):
        return {"type": "text", "value": node.text}
    elif isinstance(node, Entity):
        return {"type": "entity", "name": node.name}
    elif isinstance(node, Space):
        return {"type": "space", "name": node.name}
    else:
        return {"type": "text", "value": str(node)}


def _deserialize_condition(data: dict) -> ConditionExpr:
    """Deserialize a condition expression from dict. Returns Text('') on malformed data."""
    if not isinstance(data, dict):
        return Text("")
    t = data.get("type")
    if t == "or":
        left = data.get("left")
        right = data.get("right")
        if left is None or right is None:
            return Text("")
        return BoolOr(_deserialize_condition(left), _deserialize_condition(right))
    elif t == "and":
        left = data.get("left")
        right = data.get("right")
        if left is None or right is None:
            return Text("")
        return BoolAnd(_deserialize_condition(left), _deserialize_condition(right))
    elif t == "not":
        operand = data.get("operand")
        if operand is None:
            return Text("")
        return BoolNot(_deserialize_condition(operand))
    elif t == "compare":
        left = data.get("left")
        op = data.get("op")
        right = data.get("right")
        if left is None or op is None or right is None:
            return Text("")
        return Compare(_deserialize_condition(left), op, _deserialize_condition(right))
    elif t == "query":
        command = data.get("command")
        if command is None:
            return Text("")
        nodes = [_deserialize_node(n) for n in command]
        return SchedulerQuery(nodes)
    elif t == "text":
        return Text(data.get("value", ""))
    elif t == "entity":
        return Entity(data.get("name", ""))
    elif t == "space":
        return Space(data.get("name", ""))
    else:
        return Text("")


def _deserialize_node(data: dict):
    """Deserialize a parser node. Returns Text('') on malformed data."""
    if not isinstance(data, dict):
        return Text("")
    t = data.get("type")
    if t == "text":
        return Text(data.get("value", ""))
    elif t == "entity":
        return Entity(data.get("name", ""))
    elif t == "space":
        return Space(data.get("name", ""))
    else:
        return Text("")


class WakeInteractor(Interactor):
    r"""
    Register wake conditions for entities.

    Entities call \wake to specify when they should think next.
    Transformer polls should_wake() to check if conditions are met.

    Flow:
    1. Entity: \wake ?($(\incoming---)) Check messages ---
    2. Transformer: wake.should_wake("@alice") → (False, None)
    3. ... time passes, message arrives ...
    4. Transformer: wake.should_wake("@alice") → (True, "Check messages")
    5. Transformer builds prompt with self_prompt, calls LLM
    6. Wake record is consumed (entity must \wake again to stay active)
    """

    def __init__(self, body=None, mind=None, memory_root="memory/wake",
                 listen=None, spaces_root="memory/spaces"):
        """
        Create wake interactor.

        Args:
            body: Body instance (for state access)
            mind: Mind instance (for evaluating $() conditions)
            memory_root: Where to store wake records
            listen: ListenInteractor instance (for fetching subscriptions)
            spaces_root: Where space message files live
        """
        self.body = body
        self.mind = mind
        self.memory_root = Path(memory_root)
        self.memory_root.mkdir(parents=True, exist_ok=True)
        self.listen = listen
        self.spaces_root = Path(spaces_root)

    def _get_wake_file(self, entity: str) -> Path:
        """Get path to entity's wake record file."""
        # Sanitize entity name for filename
        safe_name = entity.replace("@", "").replace("/", "_")
        return self.memory_root / f"{safe_name}.json"

    def _load_record(self, entity: str) -> dict | None:
        """Load wake record for entity."""
        path = self._get_wake_file(entity)
        if not path.exists():
            return None
        try:
            with open(path) as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return None

    def _save_record(self, entity: str, condition_data: dict, self_prompt: str | None):
        """Save wake record for entity."""
        record = {
            "entity": entity,
            "condition": condition_data,
            "self_prompt": self_prompt
        }
        path = self._get_wake_file(entity)
        with open(path, "w") as f:
            json.dump(record, f, indent=2)

    def _clear_record(self, entity: str):
        """Remove wake record (entity has woken)."""
        path = self._get_wake_file(entity)
        if path.exists():
            path.unlink()

    def execute(self, cmd: Command, executor: str = None) -> str:
        """
        Register wake condition.

        Args:
            cmd: Parsed command with ?() condition and self-prompt
            executor: Entity registering to wake

        Returns:
            Confirmation message
        """
        if not executor:
            return "ERROR: Wake requires executor (who is sleeping?)"

        # Extract ?() condition
        condition = None
        condition_idx = -1
        for i, node in enumerate(cmd.content):
            if isinstance(node, Condition):
                condition = node
                condition_idx = i
                break

        if not condition:
            return r"ERROR: No condition found. Usage: \wake ?(condition) prompt ---"

        # Serialize the condition expression tree
        condition_data = _serialize_condition(condition.expression)

        # Extract self-prompt (text after condition)
        self_prompt_parts = []
        for node in cmd.content[condition_idx + 1:]:
            if isinstance(node, Text):
                text = node.text.strip()
                if text:
                    self_prompt_parts.append(text)

        self_prompt = " ".join(self_prompt_parts) if self_prompt_parts else None

        # Save record
        self._save_record(executor, condition_data, self_prompt)

        # Return confirmation
        if self_prompt:
            preview = self_prompt[:50] + "..." if len(self_prompt) > 50 else self_prompt
            return f"Wake registered: {preview}"
        return "Wake registered"

    async def should_wake(self, entity: str) -> tuple[bool, str | None]:
        """
        Check if entity should wake.

        Called by transformer during polling.

        Args:
            entity: Entity to check

        Returns:
            (should_wake, self_prompt) - True + prompt (with messages) if condition met
        """
        record = self._load_record(entity)
        if not record:
            return (False, None)

        condition_data = record.get("condition")
        self_prompt = record.get("self_prompt")

        if not condition_data:
            return (False, None)

        # Evaluate condition via eval interactor
        if not self.mind:
            # No mind = can't evaluate, don't wake
            return (False, None)

        try:
            # Deserialize the condition expression
            expr = _deserialize_condition(condition_data)

            # Wrap in a Condition for evaluate_condition
            condition = Condition(expr)

            # Evaluate using the eval interactor
            result = await evaluate_condition(condition, self.mind, entity)

            if result:
                # Condition met - clear record
                self._clear_record(entity)

                # Fetch messages from listened spaces
                messages = self._fetch_messages(entity)

                # Bundle self_prompt with messages
                full_prompt = self._build_prompt(self_prompt, messages)

                return (True, full_prompt)
        except Exception:
            pass

        return (False, None)

    def _fetch_messages(self, entity: str) -> list[dict]:
        """Fetch new messages from listened spaces."""
        if not self.listen:
            return []

        subscriptions = self.listen.get_subscriptions(entity)
        if not subscriptions:
            return []

        messages = []
        for sub in subscriptions:
            space_file = self._get_space_file(entity, sub)
            if space_file and space_file.exists():
                messages.extend(self._read_space_messages(space_file))

        return messages

    def _get_space_file(self, entity: str, subscription: str) -> Path | None:
        """Get space file path for a subscription."""
        if subscription.startswith("@"):
            # Entity-addressed space: sorted names joined
            members = sorted([entity, subscription])
            space_id = "-".join(members)
        elif subscription.startswith("#"):
            # Named space
            space_id = subscription
        else:
            return None

        return self.spaces_root / f"{space_id}.jsonl"

    def _read_space_messages(self, space_file: Path, limit: int = 10) -> list[dict]:
        """Read recent messages from a space file."""
        try:
            with open(space_file) as f:
                lines = f.readlines()
            # Get last N messages
            recent = lines[-limit:] if len(lines) > limit else lines
            messages = []
            for line in recent:
                line = line.strip()
                if line:
                    try:
                        messages.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
            return messages
        except OSError:
            return []

    def _build_prompt(self, self_prompt: str | None, messages: list[dict]) -> str:
        """Build full prompt with self_prompt and messages."""
        parts = []

        if self_prompt:
            parts.append(self_prompt)

        if messages:
            parts.append("\n--- Messages ---")
            for msg in messages:
                sender = msg.get("sender", "?")
                content = msg.get("content", "")
                parts.append(f"{sender}: {content}")

        return "\n".join(parts) if parts else ""

    def has_wake_record(self, entity: str) -> bool:
        """Check if entity has a pending wake record."""
        return self._load_record(entity) is not None
