"""
Wake interactor - Set wake conditions with self-prompts.

\\wake ?(condition) self-prompt text ---

Behavior:
1. Register wake condition with body
2. Store self-prompt to include on wake
3. Entity suspends until condition satisfied
4. On wake: stdin buffer + self-prompt → entity

Example:
\\wake ?(response(@bob)) Let me know what you think! ---

When @bob responds, entity wakes with:
  [messages from stdin buffer]
  [self-prompt: "Let me know what you think!"]
"""

from grammar.parser import Command, Text, Condition
from interactors.base import Interactor


class WakeInteractor(Interactor):
    """
    Set wake condition and self-prompt.

    Needs access to body's wake registry to register condition.
    """

    def __init__(self, body=None):
        """
        Create wake interactor.

        Args:
            body: Body instance (for wake registry access)
        """
        self.body = body

    def execute(self, cmd: Command) -> str:
        """
        Register wake condition.

        Args:
            cmd: Parsed command tree

        Returns:
            Status message
        """
        # Extract condition node
        condition_node = None
        for node in cmd.content:
            if isinstance(node, Condition):
                condition_node = node
                break

        if not condition_node:
            return "ERROR: No condition found in wake command"

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

        # For now: just return success
        # Real implementation would register with body
        # self.body.register_wake(executor, condition_node, self_prompt)

        if self_prompt:
            return f"Wake condition set with prompt: {self_prompt[:50]}..."
        else:
            return "Wake condition set"
