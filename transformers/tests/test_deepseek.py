"""Tests for DeepSeek transformer (stateless inference service)."""

import os
import pytest
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from transformers.deepseek import DeepSeekTransformer


def test_deepseek_requires_api_key():
    """DeepSeek transformer requires API key."""
    old_key = os.environ.pop('DEEPSEEK_API_KEY', None)

    try:
        with pytest.raises(ValueError, match="DeepSeek API key required"):
            DeepSeekTransformer()
    finally:
        if old_key:
            os.environ['DEEPSEEK_API_KEY'] = old_key


def test_deepseek_accepts_explicit_api_key():
    """DeepSeek transformer accepts explicit API key."""
    transformer = DeepSeekTransformer(api_key="test-key")
    assert transformer.api_key == "test-key"
    assert transformer.model == "deepseek-chat"


def test_deepseek_uses_env_api_key():
    """DeepSeek transformer uses DEEPSEEK_API_KEY from environment."""
    os.environ['DEEPSEEK_API_KEY'] = "env-test-key"

    try:
        transformer = DeepSeekTransformer()
        assert transformer.api_key == "env-test-key"
    finally:
        os.environ.pop('DEEPSEEK_API_KEY', None)


def test_deepseek_extracts_valid_command():
    """DeepSeek extracts command from LLM response."""
    transformer = DeepSeekTransformer(api_key="test-key")

    response = "I'll respond with a greeting.\n\n\\stdout Hello from @alice! ---"
    command = transformer._extract_command(response)

    assert command == r"\stdout Hello from @alice! ---"


def test_deepseek_extracts_first_command_only():
    """DeepSeek extracts only the first command from response."""
    transformer = DeepSeekTransformer(api_key="test-key")

    response = r"\stdout First command ---\stdout Second command ---"
    command = transformer._extract_command(response)

    assert command == r"\stdout First command ---"


def test_deepseek_returns_none_for_invalid_response():
    """DeepSeek returns None for responses without valid commands."""
    transformer = DeepSeekTransformer(api_key="test-key")

    response = "I don't know what to do."
    command = transformer._extract_command(response)

    assert command is None


def test_deepseek_system_prompt_format():
    """DeepSeek formats system prompt correctly."""
    transformer = DeepSeekTransformer(api_key="test-key")

    context = {"tick": 42}
    prompt = transformer._format_system_prompt("@alice", context)

    assert "You are @alice" in prompt
    assert "Current tick: 42" in prompt
    assert r"\stdout" in prompt
    assert r"\echo" in prompt
    assert "Available commands:" in prompt


def test_deepseek_system_prompt_includes_wake_reason():
    """DeepSeek includes wake reason in system prompt when provided."""
    transformer = DeepSeekTransformer(api_key="test-key")

    context = {"tick": 42, "wake_reason": "New message from @bob"}
    prompt = transformer._format_system_prompt("@alice", context)

    assert "You woke up because:" in prompt
    assert "New message from @bob" in prompt


@pytest.mark.asyncio
@patch('transformers.deepseek.AsyncOpenAI')
async def test_deepseek_calls_api_with_correct_params(mock_openai_class):
    """DeepSeek calls API with correct parameters."""
    mock_client = MagicMock()
    mock_openai_class.return_value = mock_client

    mock_response = Mock()
    mock_response.choices = [Mock()]
    mock_response.choices[0].message.content = r"\stdout Test ---"
    mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

    transformer = DeepSeekTransformer(api_key="test-key", model="deepseek-chat")

    context = {"tick": 0}
    result = await transformer._call_api("@alice", context)

    mock_openai_class.assert_called_once_with(
        api_key="test-key",
        base_url="https://api.deepseek.com"
    )

    mock_client.chat.completions.create.assert_called_once()
    call_kwargs = mock_client.chat.completions.create.call_args[1]

    assert call_kwargs['model'] == "deepseek-chat"
    assert call_kwargs['temperature'] == 0.7
    assert call_kwargs['max_tokens'] == 500
    assert len(call_kwargs['messages']) == 2
    assert result == r"\stdout Test ---"


@pytest.mark.asyncio
@patch('transformers.deepseek.AsyncOpenAI')
async def test_deepseek_think_full_cycle(mock_openai_class):
    """DeepSeek.think() full cycle: context → API → extract → return."""
    mock_client = MagicMock()
    mock_openai_class.return_value = mock_client

    mock_response = Mock()
    mock_response.choices = [Mock()]
    mock_response.choices[0].message.content = r"I'll say hello!\n\n\stdout Hello from DeepSeek! ---"
    mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

    transformer = DeepSeekTransformer(api_key="test-key")

    context = {"tick": 5}
    result = await transformer.think("@alice", context)

    assert result == r"\stdout Hello from DeepSeek! ---"
    mock_client.chat.completions.create.assert_called_once()


@pytest.mark.asyncio
@patch('transformers.deepseek.AsyncOpenAI')
async def test_deepseek_think_returns_none_on_invalid_response(mock_openai_class):
    """DeepSeek.think() returns None when LLM gives no valid command."""
    mock_client = MagicMock()
    mock_openai_class.return_value = mock_client

    mock_response = Mock()
    mock_response.choices = [Mock()]
    mock_response.choices[0].message.content = "I'm not sure what to do."
    mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

    transformer = DeepSeekTransformer(api_key="test-key")

    context = {"tick": 0}
    result = await transformer.think("@alice", context)

    assert result is None


@pytest.mark.skip(reason="Requires real DeepSeek API key - run manually with DEEPSEEK_API_KEY set")
@pytest.mark.asyncio
async def test_deepseek_real_api_integration():
    """Integration test with real DeepSeek API.

    To run:
    1. Set environment variable: export DEEPSEEK_API_KEY="your-key"
    2. Run with: pytest transformers/tests/test_deepseek.py::test_deepseek_real_api_integration -v
    """
    api_key = os.getenv('DEEPSEEK_API_KEY')
    if not api_key:
        pytest.skip("DEEPSEEK_API_KEY not set")

    transformer = DeepSeekTransformer(api_key=api_key)
    context = {"tick": 0}

    result = await transformer.think("@alice", context)

    assert result is not None
    assert result.startswith("\\")
    assert result.endswith("---")
    print(f"\nDeepSeek response: {result}")
