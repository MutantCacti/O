"""Tests for DeepSeek transformer."""

import os
import pytest
from unittest.mock import Mock, patch, MagicMock
from transformers.deepseek import DeepSeekTransformer
from mind import Mind
from state.state import SystemState
from body import Body


def test_deepseek_requires_api_key():
    """DeepSeek transformer requires API key."""
    # Remove env var if present
    old_key = os.environ.pop('DEEPSEEK_API_KEY', None)

    try:
        with pytest.raises(ValueError, match="DeepSeek API key required"):
            DeepSeekTransformer(entity="@alice")
    finally:
        # Restore env var
        if old_key:
            os.environ['DEEPSEEK_API_KEY'] = old_key


def test_deepseek_accepts_explicit_api_key():
    """DeepSeek transformer accepts explicit API key."""
    transformer = DeepSeekTransformer(entity="@alice", api_key="test-key")
    assert transformer.api_key == "test-key"
    assert transformer.entity == "@alice"
    assert transformer.model == "deepseek-chat"


def test_deepseek_uses_env_api_key():
    """DeepSeek transformer uses DEEPSEEK_API_KEY from environment."""
    os.environ['DEEPSEEK_API_KEY'] = "env-test-key"

    try:
        transformer = DeepSeekTransformer(entity="@alice")
        assert transformer.api_key == "env-test-key"
    finally:
        os.environ.pop('DEEPSEEK_API_KEY', None)


def test_deepseek_throttles_per_tick():
    """DeepSeek only responds once per tick."""
    transformer = DeepSeekTransformer(entity="@alice", api_key="test-key")

    # Mock the API call
    with patch.object(transformer, '_call_api', return_value=r"\stdout Hello ---"):
        mind = Mind({})
        state = SystemState(tick=0, executions=[])
        body = Body(mind, state)

        # First poll at tick 0 - should respond
        result1 = transformer.poll(body)
        assert result1 is not None
        assert result1[0] == "@alice"

        # Second poll at same tick - should return None
        result2 = transformer.poll(body)
        assert result2 is None

        # Advance tick
        state.advance_tick()

        # Third poll at tick 1 - should respond again
        result3 = transformer.poll(body)
        assert result3 is not None


def test_deepseek_builds_minimal_context():
    """DeepSeek builds context with entity and tick."""
    transformer = DeepSeekTransformer(entity="@alice", api_key="test-key")

    mind = Mind({})
    state = SystemState(tick=42, executions=[])
    body = Body(mind, state)

    context = transformer._build_context(body)

    assert context["entity"] == "@alice"
    assert context["tick"] == 42


def test_deepseek_extracts_valid_command():
    """DeepSeek extracts command from LLM response."""
    transformer = DeepSeekTransformer(entity="@alice", api_key="test-key")

    # Response with valid command
    response = "I'll respond with a greeting.\n\n\\stdout Hello from @alice! ---"
    command = transformer._extract_command(response)

    assert command == r"\stdout Hello from @alice! ---"


def test_deepseek_extracts_first_command_only():
    """DeepSeek extracts only the first command from response."""
    transformer = DeepSeekTransformer(entity="@alice", api_key="test-key")

    # Response with multiple commands
    response = r"\stdout First command ---\stdout Second command ---"
    command = transformer._extract_command(response)

    assert command == r"\stdout First command ---"


def test_deepseek_fallback_for_invalid_response():
    """DeepSeek provides fallback for responses without valid commands."""
    transformer = DeepSeekTransformer(entity="@alice", api_key="test-key")

    # Response without command
    response = "I don't know what to do."
    command = transformer._extract_command(response)

    assert command.startswith(r"\stdout [LLM response had no valid command:")
    assert "I don't know what to do" in command


def test_deepseek_system_prompt_format():
    """DeepSeek formats system prompt correctly."""
    transformer = DeepSeekTransformer(entity="@alice", api_key="test-key")

    context = {"entity": "@alice", "tick": 42}
    prompt = transformer._format_system_prompt(context)

    assert "You are @alice" in prompt
    assert "Current tick: 42" in prompt
    assert r"\stdout" in prompt
    assert r"\echo" in prompt
    assert "Available commands:" in prompt


@patch('transformers.deepseek.OpenAI')
def test_deepseek_calls_api_with_correct_params(mock_openai_class):
    """DeepSeek calls API with correct parameters."""
    # Mock the OpenAI client and response
    mock_client = MagicMock()
    mock_openai_class.return_value = mock_client

    mock_response = Mock()
    mock_response.choices = [Mock()]
    mock_response.choices[0].message.content = r"\stdout Test ---"
    mock_client.chat.completions.create.return_value = mock_response

    transformer = DeepSeekTransformer(entity="@alice", api_key="test-key", model="deepseek-chat")

    context = {"entity": "@alice", "tick": 0}
    result = transformer._call_api(context)

    # Verify OpenAI client initialized correctly
    mock_openai_class.assert_called_once_with(
        api_key="test-key",
        base_url="https://api.deepseek.com"
    )

    # Verify API call
    mock_client.chat.completions.create.assert_called_once()
    call_kwargs = mock_client.chat.completions.create.call_args[1]

    assert call_kwargs['model'] == "deepseek-chat"
    assert call_kwargs['temperature'] == 0.7
    assert call_kwargs['max_tokens'] == 500
    assert len(call_kwargs['messages']) == 2
    assert call_kwargs['messages'][0]['role'] == 'system'
    assert call_kwargs['messages'][1]['role'] == 'user'
    assert result == r"\stdout Test ---"


@patch('transformers.deepseek.OpenAI')
def test_deepseek_full_poll_cycle(mock_openai_class):
    """DeepSeek full poll cycle: context → API → extract → return."""
    # Mock the OpenAI client and response
    mock_client = MagicMock()
    mock_openai_class.return_value = mock_client

    mock_response = Mock()
    mock_response.choices = [Mock()]
    mock_response.choices[0].message.content = r"I'll say hello!\n\n\stdout Hello from DeepSeek! ---"
    mock_client.chat.completions.create.return_value = mock_response

    transformer = DeepSeekTransformer(entity="@alice", api_key="test-key")

    mind = Mind({})
    state = SystemState(tick=5, executions=[])
    body = Body(mind, state)

    result = transformer.poll(body)

    assert result is not None
    assert result[0] == "@alice"
    assert result[1] == r"\stdout Hello from DeepSeek! ---"

    # Verify API was called
    mock_client.chat.completions.create.assert_called_once()


@pytest.mark.skip(reason="Requires real DeepSeek API key - run manually with DEEPSEEK_API_KEY set")
def test_deepseek_real_api_integration():
    """Integration test with real DeepSeek API.

    To run:
    1. Set environment variable: export DEEPSEEK_API_KEY="your-key"
    2. Run with: pytest transformers/tests/test_deepseek.py::test_deepseek_real_api_integration -v
    """
    # This test is skipped by default - remove skip decorator to run manually
    api_key = os.getenv('DEEPSEEK_API_KEY')
    if not api_key:
        pytest.skip("DEEPSEEK_API_KEY not set")

    from interactors.echo import EchoInteractor
    from interactors.stdout import StdoutInteractor

    # Setup full system
    mind = Mind({
        "echo": EchoInteractor(),
        "stdout": StdoutInteractor()
    })
    state = SystemState(tick=0, executions=[])
    transformer = DeepSeekTransformer(entity="@alice", api_key=api_key)
    body = Body(mind, state, transformers=[transformer])

    # Run one tick
    body.tick()

    # Verify execution happened
    assert len(state.executions) > 0
    execution = state.executions[0]
    assert execution.executor == "@alice"
    assert execution.command.startswith("\\")
    assert execution.command.endswith("---")

    print(f"\nDeepSeek response: {execution.command}")
    print(f"Output: {execution.output}")
