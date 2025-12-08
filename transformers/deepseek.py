"""
DeepSeek transformer - stateless LLM inference service.

Calls DeepSeek API to generate commands for any entity.
Transformer is stateless - Body owns entities and their state.
"""

import os
import re
from typing import Optional, Dict, Any
from openai import AsyncOpenAI

from .base import Transformer


class DeepSeekTransformer(Transformer):
    """
    Stateless LLM service that generates commands via DeepSeek API.

    Body calls think(entity, context) when an entity needs to act.
    Transformer doesn't own entities - it serves them.
    """

    def __init__(
        self,
        api_key: str = None,
        model: str = "deepseek-chat"
    ):
        """
        Initialize DeepSeek transformer service.

        Args:
            api_key: DeepSeek API key (defaults to DEEPSEEK_API_KEY env var)
            model: Model name (default: deepseek-chat)
        """
        self.api_key = api_key or os.getenv('DEEPSEEK_API_KEY')
        self.model = model

        if not self.api_key:
            raise ValueError("DeepSeek API key required (DEEPSEEK_API_KEY env var or api_key parameter)")

        # Initialize async OpenAI client with DeepSeek base URL
        self.client = AsyncOpenAI(
            api_key=self.api_key,
            base_url="https://api.deepseek.com"
        )

    async def think(self, entity: str, context: Dict[str, Any]) -> Optional[str]:
        """
        Generate a command for an entity given context.

        Args:
            entity: Entity name (e.g., "@alice")
            context: Dict with entity's view of the world

        Returns:
            Command string, or None if generation failed
        """
        # Call DeepSeek API
        response = await self._call_api(entity, context)

        # Extract command from response
        return self._extract_command(response)

    async def _call_api(self, entity: str, context: Dict[str, Any]) -> str:
        """
        Call DeepSeek API with context.

        DeepSeek is stateless - full context sent each call.
        Automatic caching handles repeated system prompts efficiently.
        """
        system_prompt = self._format_system_prompt(entity, context)

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": "What do you want to do?"}
        ]

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=0.7,
            max_tokens=500,
        )

        return response.choices[0].message.content

    def _format_system_prompt(self, entity: str, context: Dict[str, Any]) -> str:
        """Format context into system prompt."""
        tick = context.get('tick', 0)
        wake_reason = context.get('wake_reason', '')

        prompt = f"""You are {entity}, an entity in the O system.
Current tick: {tick}
"""
        if wake_reason:
            prompt += f"You woke up because: {wake_reason}\n"

        prompt += """
Respond with a single O command to execute.
Format: \\command arguments ---

Available commands:
- \\stdout message ---    (write to your log)
- \\echo message ---      (echo back text)
"""
        prompt += f"\nExample: \\stdout Hello from {entity} at tick {tick} ---"
        return prompt

    def _extract_command(self, response: str) -> Optional[str]:
        """
        Extract O command from LLM response.

        Looks for pattern: \\command ... ---
        Returns None if no valid command found (caller decides fallback).
        """
        # Pattern: backslash + word + content + triple dash
        pattern = r'\\[^\\]+?---'
        matches = re.findall(pattern, response, re.DOTALL)

        if matches:
            # Return first command found, stripped
            return matches[0].strip()

        # No valid command found
        return None
