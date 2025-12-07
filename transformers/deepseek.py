"""
DeepSeek transformer - LLM entity I/O device.

Minimal implementation: polls body state, calls DeepSeek, returns command.
No wake conditions yet - just demonstrates the transformer pattern with real LLM.
"""

import os
import re
from typing import Optional, Tuple, Dict, Any
from openai import OpenAI

from .base import Transformer


class DeepSeekTransformer(Transformer):
    """
    LLM entity that generates commands via DeepSeek API.

    Minimal MVP: Always responds when polled (no wake checking).
    Demonstrates transformer → LLM → command flow.
    """

    def __init__(
        self,
        entity: str,
        api_key: str = None,
        model: str = "deepseek-chat"
    ):
        """
        Initialize DeepSeek transformer.

        Args:
            entity: Entity name (e.g., "@alice")
            api_key: DeepSeek API key (defaults to DEEPSEEK_API_KEY env var)
            model: Model name (default: deepseek-chat)
        """
        self.entity = entity
        self.api_key = api_key or os.getenv('DEEPSEEK_API_KEY')
        self.model = model

        if not self.api_key:
            raise ValueError("DeepSeek API key required (DEEPSEEK_API_KEY env var or api_key parameter)")

        # Initialize OpenAI client with DeepSeek base URL
        self.client = OpenAI(
            api_key=self.api_key,
            base_url="https://api.deepseek.com"
        )

        # Track whether we've responded this tick (simple throttle)
        self._responded_this_tick = False
        self._last_tick = -1

    def poll(self, body) -> Optional[Tuple[str, str]]:
        """
        Poll body state, call DeepSeek, return command.

        MVP: Responds once per tick with simple context.

        Args:
            body: Body instance (full system context)

        Returns:
            (entity, command) tuple, or None if already responded this tick
        """
        # Simple throttle: only respond once per tick
        if body.state.tick == self._last_tick:
            return None

        # Build context
        context = self._build_context(body)

        # Call DeepSeek API
        response = self._call_api(context)

        # Extract command
        command = self._extract_command(response)

        # Update throttle
        self._last_tick = body.state.tick

        return (self.entity, command)

    def _build_context(self, body) -> Dict[str, Any]:
        """
        Build minimal context for LLM.

        MVP: Just entity identity and current tick.
        Future: Add spaces, history, messages, etc.
        """
        return {
            "entity": self.entity,
            "tick": body.state.tick,
        }

    def _call_api(self, context: Dict[str, Any]) -> str:
        """
        Call DeepSeek API with context.

        DeepSeek is stateless - full context sent each call.
        Automatic caching handles repeated system prompts efficiently.
        """
        system_prompt = self._format_system_prompt(context)

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": "What do you want to do?"}
        ]

        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=0.7,
            max_tokens=500,
        )

        return response.choices[0].message.content

    def _format_system_prompt(self, context: Dict[str, Any]) -> str:
        """Format context into system prompt."""
        return f"""You are {context['entity']}, an entity in the O system.
Current tick: {context['tick']}

Respond with a single O command to execute.
Format: \\command arguments ---

Available commands:
- \\stdout message ---    (write to your log)
- \\echo message ---      (echo back text)

Example: \\stdout Hello from {context['entity']} at tick {context['tick']} ---"""

    def _extract_command(self, response: str) -> str:
        """
        Extract O command from LLM response.

        Looks for pattern: \\command ... ---
        Falls back to logging if no valid command found.
        """
        # Pattern: backslash + word + content + triple dash
        pattern = r'\\[^\\]+?---'
        matches = re.findall(pattern, response, re.DOTALL)

        if matches:
            # Return first command found, stripped
            return matches[0].strip()

        # Fallback: log the response
        safe_response = response.replace('\\', '\\\\').replace('---', '').strip()[:100]
        return f"\\stdout [LLM response had no valid command: {safe_response}] ---"
