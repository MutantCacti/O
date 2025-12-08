"""
Transformer base class - stateless inference services for O.

Transformers are inference providers (LLMs, human input) that Body uses
to generate commands for entities. They are stateless services - they don't
own entities, they serve them.

Body owns entities. Body decides when entities wake. Body calls transformers
to generate commands for awake entities.

All transformers are async for safe concurrent I/O.
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any


class Transformer(ABC):
    """
    Abstract inference service that generates commands for entities.

    Transformers are STATELESS. They don't own entities - Body does.
    Body calls transformer.think(entity, context) when an entity needs to act.

    Different transformer types:
    - LLMTransformer: Calls LLM API (DeepSeek, Anthropic, etc.)
    - HumanTransformer: Queues human input, returns when available

    Body doesn't care about the difference - it just asks for commands.
    """

    @abstractmethod
    async def think(self, entity: str, context: Dict[str, Any]) -> Optional[str]:
        """
        Generate a command for an entity given context.

        Args:
            entity: Entity name (e.g., "@alice")
            context: Dict with entity's view of the world:
                - tick: Current tick number
                - spaces: Spaces entity is in
                - messages: Recent messages in those spaces
                - stdout: Entity's recent stdout
                - wake_reason: Why entity woke up (if applicable)

        Returns:
            Command string (e.g., "\\say #general Hello! ---")
            None if no command generated

        Note: This is a stateless call. Transformer should not store
        per-entity state. All context comes from the Body.
        """
        pass
