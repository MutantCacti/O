"""
Wake interactor - Register wake conditions.

\\wake ?(condition) self-prompt text ---

Entities use this to suspend and specify when to wake.
Transformer evaluates condition during polling.

Example:
\\wake ?(response(@bob)) Check what Bob said ---

When @bob responds, transformer wakes entity with self-prompt.
"""

from grammar.parser import Command, Text, Condition
from interactors.base import Interactor


class WakeInteractor(Interactor):
    """
    Register wake condition for entity.

    Interactor stores condition + self-prompt in body.sleep_queue.
    Transformer checks condition during poll(), wakes when satisfied.
    """

    def __init__(self, body=None):
        """
        Create wake interactor.

        Args:
            body: Body instance (for sleep_queue access)
        """
        self.body = body

    def execute(self, cmd: Command, executor: str = None) -> str:
        """
        Register wake condition.

        Args:
            cmd: Parsed command tree
            executor: Entity registering wake condition

        Returns:
            Status message
        """
        if not executor:
            return "ERROR: Wake requires executor (who is sleeping?)"

        # Extract condition node
        condition_node = None
        for node in cmd.content:
            if isinstance(node, Condition):
                condition_node = node
                break

        if not condition_node:
            return "ERROR: No condition found. Usage: \\wake ?(condition) prompt ---"

        # Extract self-prompt (all text after condition)
        self_prompt_parts = []
        found_condition = False

        for node in cmd.content:
            if isinstance(node, Condition):
                found_condition = True
                continue

            if found_condition and isinstance(node, Text):
                text = node.text.strip()
                if text:
                    self_prompt_parts.append(text)

        self_prompt = " ".join(self_prompt_parts) if self_prompt_parts else None

        # Guard: Need body to register wake condition
        if not self.body:
            prompt_preview = f" with prompt: {self_prompt[:30]}..." if self_prompt else ""
            return f"Would register wake for {executor}{prompt_preview} (body not connected)"

        # Register with body's sleep queue
        from body import WakeRecord

        self.body.sleep_queue[executor] = WakeRecord(
            entity=executor,
            condition=condition_node,
            self_prompt=self_prompt,
            resume_command=None
        )

        # Return success
        if self_prompt:
            prompt_preview = self_prompt[:50] + "..." if len(self_prompt) > 50 else self_prompt
            return f"Registered wake condition with prompt: {prompt_preview}"
        else:
            return "Registered wake condition"
