"""Test Body polling transformers for input."""

import pytest
from transformers.human import HumanTransformer
from mind import Mind
from body import Body
from state.state import SystemState
from interactors.echo import EchoInteractor
from interactors.stdout import StdoutInteractor
from pathlib import Path
import shutil
import json


@pytest.fixture
def test_memory_dir(tmp_path):
    """Create temporary memory directory."""
    memory_dir = tmp_path / "memory" / "stdout"
    memory_dir.mkdir(parents=True)
    yield memory_dir
    if memory_dir.parent.exists():
        shutil.rmtree(memory_dir.parent)


def test_body_polls_transformer_directly():
    """Body can poll transformer and get commands without tick()."""
    human = HumanTransformer()
    mind = Mind({"echo": EchoInteractor()})
    state = SystemState(tick=0, executions=[])
    body = Body(mind, state, transformers=[human])

    # Human submits command
    human.submit("@alice", r"\echo Hello! ---")

    # Poll directly (what tick() does)
    result = human.poll(body)
    assert result == ("@alice", r"\echo Hello! ---")

    # Execute
    entity, command = result
    output = body.execute_now(entity, command)

    # Verify
    assert "Hello!" in output
    assert len(state.executions) == 1


def test_body_polls_transformer_on_tick():
    """Body.tick() polls transformers and executes commands."""
    human = HumanTransformer()
    mind = Mind({"echo": EchoInteractor()})
    state = SystemState(tick=0, executions=[])
    body = Body(mind, state, transformers=[human])

    # Human submits command
    human.submit("@alice", r"\echo Hello from Alice! ---")

    # Tick - Body polls transformer and executes
    body.tick()

    # Check log file was created
    log_file = Path("state/logs/log_0.json")
    assert log_file.exists()

    # Read log to verify execution
    with open(log_file) as f:
        log_data = json.load(f)

    assert log_data["tick"] == 0
    assert len(log_data["executions"]) == 1
    assert log_data["executions"][0]["executor"] == "@alice"
    assert "Hello from Alice!" in log_data["executions"][0]["output"]

    # Tick advanced
    assert state.tick == 1

    # Cleanup
    shutil.rmtree("state/logs")


def test_body_polls_multiple_transformers():
    """Body polls all transformers in order."""
    human1 = HumanTransformer()
    human2 = HumanTransformer()

    mind = Mind({"echo": EchoInteractor()})
    state = SystemState(tick=0, executions=[])
    body = Body(mind, state, transformers=[human1, human2])

    # Both submit commands
    human1.submit("@alice", r"\echo Alice here ---")
    human2.submit("@bob", r"\echo Bob here ---")

    # Single tick polls both
    body.tick()

    # Check log
    log_file = Path("state/logs/log_0.json")
    assert log_file.exists()

    with open(log_file) as f:
        log_data = json.load(f)

    assert len(log_data["executions"]) == 2
    assert log_data["executions"][0]["executor"] == "@alice"
    assert log_data["executions"][1]["executor"] == "@bob"

    # Cleanup
    shutil.rmtree("state/logs")


def test_body_tick_empty_when_no_input():
    """Body.tick() with no transformer input does nothing."""
    human = HumanTransformer()
    mind = Mind({"echo": EchoInteractor()})
    state = SystemState(tick=0, executions=[])
    body = Body(mind, state, transformers=[human])

    # Tick with no input
    body.tick()

    # No log file created (no executions)
    log_file = Path("state/logs/log_0.json")
    assert not log_file.exists()

    # But tick still advanced
    assert state.tick == 1


def test_body_with_stdout_interactor(test_memory_dir):
    """Body polls transformer and executes stdout commands."""
    human = HumanTransformer()
    stdout_int = StdoutInteractor(memory_root=str(test_memory_dir))

    mind = Mind({"stdout": stdout_int})
    state = SystemState(tick=0, executions=[])
    body = Body(mind, state, transformers=[human])

    # Connect stdout to body
    stdout_int.body = body

    # Human writes to stdout
    human.submit("@alice", r"\stdout First log entry ---")

    # Tick executes
    body.tick()

    # Check execution log
    log_file = Path("state/logs/log_0.json")
    assert log_file.exists()

    with open(log_file) as f:
        log_data = json.load(f)

    assert "Written to stdout" in log_data["executions"][0]["output"]

    # Verify persisted
    stdout_file = test_memory_dir / "@alice.jsonl"
    assert stdout_file.exists()

    # Cleanup
    shutil.rmtree("state/logs")


def test_body_multiple_ticks_with_input():
    """Body can process input across multiple ticks."""
    human = HumanTransformer()
    mind = Mind({"echo": EchoInteractor()})
    state = SystemState(tick=0, executions=[])
    body = Body(mind, state, transformers=[human])

    # Tick 1: Input available
    human.submit("@alice", r"\echo Tick 1 ---")
    body.tick()
    assert state.tick == 1

    log_1 = Path("state/logs/log_0.json")
    assert log_1.exists()

    # Tick 2: No input
    body.tick()
    assert state.tick == 2
    # No log for tick 1 (no executions)

    # Tick 3: Input again
    human.submit("@bob", r"\echo Tick 3 ---")
    body.tick()
    assert state.tick == 3

    log_3 = Path("state/logs/log_2.json")
    assert log_3.exists()

    # Cleanup
    shutil.rmtree("state/logs")
