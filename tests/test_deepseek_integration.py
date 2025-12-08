"""Integration test for DeepSeek transformer with Body.tick() flow."""

import json
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from transformers.deepseek import DeepSeekTransformer
from interactors.echo import EchoInteractor
from interactors.stdout import StdoutInteractor
from mind import Mind
from state.state import SystemState
from body import Body


def test_body_polls_deepseek_executes_command(tmp_path):
    """Full integration: Body.tick() → DeepSeek.poll() → Mind.execute() → State.log()."""

    # Setup Mind with interactors (use tmp_path for isolation)
    stdout = StdoutInteractor(memory_root=str(tmp_path / "stdout"))
    mind = Mind({
        "echo": EchoInteractor(),
        "stdout": stdout
    })

    # Setup State with temp log directory
    state = SystemState(tick=0, executions=[])

    # Mock DeepSeek API
    with patch('transformers.deepseek.OpenAI') as mock_openai_class:
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client

        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = r"\stdout Hello from DeepSeek at tick 0! ---"
        mock_client.chat.completions.create.return_value = mock_response

        # Create transformer and body
        transformer = DeepSeekTransformer(entity="@alice", api_key="test-key")
        body = Body(mind, state, transformers=[transformer])

        # Run one tick
        body.tick()

        # Verify API was called
        mock_client.chat.completions.create.assert_called_once()

        # Verify command was executed and logged
        log_file = Path("state/logs/log_0.json")
        assert log_file.exists()

        with open(log_file) as f:
            log_data = json.load(f)

        assert log_data["tick"] == 0
        assert len(log_data["executions"]) == 1

        execution = log_data["executions"][0]
        assert execution["executor"] == "@alice"
        assert execution["command"] == r"\stdout Hello from DeepSeek at tick 0! ---"
        assert "Written to stdout" in execution["output"]

        # Verify tick advanced
        assert state.tick == 1

        # Clean up
        log_file.unlink()


def test_deepseek_throttles_across_ticks(tmp_path):
    """DeepSeek only responds once per tick, but responds again next tick."""

    stdout = StdoutInteractor(memory_root=str(tmp_path / "stdout"))
    mind = Mind({"stdout": stdout})
    state = SystemState(tick=0, executions=[])

    with patch('transformers.deepseek.OpenAI') as mock_openai_class:
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client

        # Different response each time (but only called once per tick)
        responses = [
            r"\stdout Tick 0 response ---",
            r"\stdout Tick 1 response ---",
        ]
        mock_response = Mock()
        mock_response.choices = [Mock()]

        call_count = [0]

        def get_response(*args, **kwargs):
            response = Mock()
            response.choices = [Mock()]
            response.choices[0].message.content = responses[call_count[0]]
            call_count[0] += 1
            return response

        mock_client.chat.completions.create.side_effect = get_response

        transformer = DeepSeekTransformer(entity="@alice", api_key="test-key")
        body = Body(mind, state, transformers=[transformer])

        # Tick 0
        body.tick()

        # Verify first response
        log_0 = Path("state/logs/log_0.json")
        assert log_0.exists()
        with open(log_0) as f:
            data = json.load(f)
        assert data["executions"][0]["command"] == r"\stdout Tick 0 response ---"

        # Tick 1
        body.tick()

        # Verify second response
        log_1 = Path("state/logs/log_1.json")
        assert log_1.exists()
        with open(log_1) as f:
            data = json.load(f)
        assert data["executions"][0]["command"] == r"\stdout Tick 1 response ---"

        # Verify API was called exactly twice (once per tick)
        assert mock_client.chat.completions.create.call_count == 2

        # Clean up
        log_0.unlink()
        log_1.unlink()


def test_deepseek_with_multiple_transformers():
    """Multiple transformers can coexist - DeepSeek + Human."""

    from transformers.human import HumanTransformer

    mind = Mind({"echo": EchoInteractor()})
    state = SystemState(tick=0, executions=[])

    with patch('transformers.deepseek.OpenAI') as mock_openai_class:
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client

        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = r"\echo Alice says hello ---"
        mock_client.chat.completions.create.return_value = mock_response

        # Create both transformers
        deepseek = DeepSeekTransformer(entity="@alice", api_key="test-key")
        human = HumanTransformer()

        # Queue human input
        human.submit("@bob", r"\echo Bob says hi ---")

        body = Body(mind, state, transformers=[deepseek, human])

        # Run one tick - both should respond
        body.tick()

        # Verify both commands executed
        log_file = Path("state/logs/log_0.json")
        assert log_file.exists()

        with open(log_file) as f:
            log_data = json.load(f)

        assert len(log_data["executions"]) == 2

        # Find each execution (order may vary)
        alice_exec = next(e for e in log_data["executions"] if e["executor"] == "@alice")
        bob_exec = next(e for e in log_data["executions"] if e["executor"] == "@bob")

        assert "Alice says hello" in alice_exec["output"]
        assert "Bob says hi" in bob_exec["output"]

        # Clean up
        log_file.unlink()


def test_deepseek_fallback_on_invalid_response(tmp_path):
    """When DeepSeek returns invalid response, fallback command is logged."""

    stdout = StdoutInteractor(memory_root=str(tmp_path / "stdout"))
    mind = Mind({"stdout": stdout})
    state = SystemState(tick=0, executions=[])

    with patch('transformers.deepseek.OpenAI') as mock_openai_class:
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client

        # Response without valid O command
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "I don't understand the O language yet."
        mock_client.chat.completions.create.return_value = mock_response

        transformer = DeepSeekTransformer(entity="@alice", api_key="test-key")
        body = Body(mind, state, transformers=[transformer])

        body.tick()

        # Verify fallback command was executed
        log_file = Path("state/logs/log_0.json")
        assert log_file.exists()

        with open(log_file) as f:
            log_data = json.load(f)

        execution = log_data["executions"][0]
        assert execution["command"].startswith(r"\stdout [LLM response had no valid command:")
        assert "I don't understand" in execution["command"]

        # Clean up
        log_file.unlink()
