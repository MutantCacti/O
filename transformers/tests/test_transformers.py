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
    async def test_read_command_returns_none_when_empty(self):
        """read_command() returns None when no input submitted."""
        human = HumanTransformer()
        result = await human.read_command("@alice")
        assert result is None

    @pytest.mark.asyncio
    async def test_read_command_returns_submitted(self):
        """read_command() returns submitted command."""
        human = HumanTransformer()
        human.submit("@alice", r"\echo Hello ---")

        result = await human.read_command("@alice")
        assert result == r"\echo Hello ---"

    @pytest.mark.asyncio
    async def test_read_command_clears_after_read(self):
        """read_command() clears pending after successful read."""
        human = HumanTransformer()
        human.submit("@alice", r"\echo Hello ---")

        # First call returns command
        result = await human.read_command("@alice")
        assert result == r"\echo Hello ---"

        # Second call returns None (cleared)
        result = await human.read_command("@alice")
        assert result is None

    @pytest.mark.asyncio
    async def test_write_output_stores_result(self):
        """write_output() stores result for retrieval."""
        human = HumanTransformer()
        await human.write_output("@alice", {"tick": 0, "output": "test"})

        outputs = human.get_outputs("@alice")
        assert len(outputs) == 1
        assert outputs[0]["output"] == "test"

    def test_submit_stores_command(self):
        """submit() stores command for entity."""
        human = HumanTransformer()
        human.submit("@bob", r"\stdout Test ---")

        assert "@bob" in human._pending
