"""Test transformer base class and HumanTransformer stub."""

import pytest
from transformers.base import Transformer
from transformers.human import HumanTransformer


def test_transformer_base_is_abstract():
    """Transformer is abstract - cannot instantiate directly."""
    with pytest.raises(TypeError):
        Transformer()


class TestHumanTransformerStub:
    """Test HumanTransformer reference stub."""

    def test_human_transformer_is_transformer(self):
        """HumanTransformer implements Transformer."""
        human = HumanTransformer()
        assert isinstance(human, Transformer)

    @pytest.mark.asyncio
    async def test_think_returns_none_when_empty(self):
        """think() returns None when no input submitted."""
        human = HumanTransformer()
        result = await human.think("@alice", {"tick": 0})
        assert result is None

    @pytest.mark.asyncio
    async def test_think_returns_command_for_matching_entity(self):
        """think() returns submitted command for matching entity."""
        human = HumanTransformer()
        human.submit("@alice", r"\echo Hello ---")

        result = await human.think("@alice", {"tick": 0})
        assert result == r"\echo Hello ---"

    @pytest.mark.asyncio
    async def test_think_returns_none_for_wrong_entity(self):
        """think() returns None if entity doesn't match."""
        human = HumanTransformer()
        human.submit("@alice", r"\echo Hello ---")

        result = await human.think("@bob", {"tick": 0})
        assert result is None

        # Command still pending for @alice
        result = await human.think("@alice", {"tick": 0})
        assert result == r"\echo Hello ---"

    @pytest.mark.asyncio
    async def test_think_clears_after_match(self):
        """think() clears pending input after successful match."""
        human = HumanTransformer()
        human.submit("@alice", r"\echo Hello ---")

        # First call returns command
        result = await human.think("@alice", {"tick": 0})
        assert result == r"\echo Hello ---"

        # Second call returns None (cleared)
        result = await human.think("@alice", {"tick": 0})
        assert result is None

    def test_submit_stores_entity_and_command(self):
        """submit() stores entity and command tuple."""
        human = HumanTransformer()
        human.submit("@bob", r"\stdout Test ---")

        assert human.pending_input == ("@bob", r"\stdout Test ---")
