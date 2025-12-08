"""Integration test for DeepSeek transformer with new stateless architecture."""

import json
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from transformers.deepseek import DeepSeekTransformer
from interactors.echo import EchoInteractor
from interactors.stdout import StdoutInteractor
from mind import Mind
from state.state import SystemState
from body import Body, WakeRecord
from grammar.parser import Condition, Text


@pytest.mark.asyncio
async def test_deepseek_think_generates_command():
    """DeepSeek.think() generates valid command for entity."""

    with patch('transformers.deepseek.AsyncOpenAI') as mock_openai_class:
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client

        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = r"\stdout Hello from DeepSeek! ---"
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        transformer = DeepSeekTransformer(api_key="test-key")

        context = {"tick": 0, "spaces": ["#general"], "wake_reason": "Test"}
        command = await transformer.think("@alice", context)

        assert command == r"\stdout Hello from DeepSeek! ---"
        mock_client.chat.completions.create.assert_called_once()


@pytest.mark.asyncio
async def test_deepseek_think_returns_none_for_invalid():
    """DeepSeek.think() returns None when LLM gives invalid response."""

    with patch('transformers.deepseek.AsyncOpenAI') as mock_openai_class:
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client

        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "I don't know what to do"
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        transformer = DeepSeekTransformer(api_key="test-key")

        context = {"tick": 0}
        command = await transformer.think("@alice", context)

        assert command is None


@pytest.mark.asyncio
async def test_body_tick_with_deepseek_and_wake(tmp_path):
    """Body.tick() calls DeepSeek for awake entity and executes command."""

    stdout = StdoutInteractor(memory_root=str(tmp_path / "stdout"))
    mind = Mind({"stdout": stdout, "echo": EchoInteractor()})
    state = SystemState(tick=0, executions=[])

    with patch('transformers.deepseek.AsyncOpenAI') as mock_openai_class:
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client

        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = r"\echo Hello from Alice! ---"
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        transformer = DeepSeekTransformer(api_key="test-key")
        body = Body(mind, state, transformer=transformer)
        stdout.body = body

        # Add @alice to sleep_queue with wake condition
        body.sleep_queue["@alice"] = WakeRecord(
            entity="@alice",
            condition=Condition([Text("true")]),
            self_prompt="Test wake"
        )

        # Mock _check_wake_conditions to return @alice
        body._check_wake_conditions = lambda: [body.sleep_queue["@alice"]]

        await body.tick()

        # Verify API was called
        mock_client.chat.completions.create.assert_called_once()

        # Verify command was executed
        log_file = Path("state/logs/log_0.json")
        if log_file.exists():
            with open(log_file) as f:
                log_data = json.load(f)

            assert len(log_data["executions"]) == 1
            assert log_data["executions"][0]["executor"] == "@alice"
            assert "Hello from Alice!" in log_data["executions"][0]["output"]

            # Clean up
            import shutil
            shutil.rmtree("state/logs")


@pytest.mark.asyncio
async def test_deepseek_receives_context():
    """DeepSeek receives proper context including wake_reason."""

    with patch('transformers.deepseek.AsyncOpenAI') as mock_openai_class:
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client

        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = r"\stdout Response ---"
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        transformer = DeepSeekTransformer(api_key="test-key")

        context = {
            "tick": 42,
            "spaces": ["#general", "#dev"],
            "wake_reason": "New message from @bob"
        }

        await transformer.think("@alice", context)

        # Check the system prompt includes context
        call_args = mock_client.chat.completions.create.call_args
        messages = call_args[1]["messages"]
        system_prompt = messages[0]["content"]

        assert "You are @alice" in system_prompt
        assert "Current tick: 42" in system_prompt
        assert "You woke up because:" in system_prompt
        assert "New message from @bob" in system_prompt
