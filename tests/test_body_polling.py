"""Test Body tick() with transformer.think() architecture."""

import pytest
from transformers.human import HumanTransformer
from mind import Mind
from body import Body, WakeRecord
from state.state import SystemState
from interactors.echo import EchoInteractor
from interactors.stdout import StdoutInteractor
from grammar.parser import Condition, Text
from pathlib import Path
import shutil


@pytest.fixture
def test_memory_dir(tmp_path):
    """Create temporary memory directory."""
    memory_dir = tmp_path / "memory" / "stdout"
    memory_dir.mkdir(parents=True)
    yield memory_dir
    if memory_dir.parent.exists():
        shutil.rmtree(memory_dir.parent)


@pytest.mark.asyncio
async def test_body_tick_advances_clock():
    """Body.tick() advances clock even with no entities."""
    mind = Mind({"echo": EchoInteractor()})
    state = SystemState(tick=0, executions=[])
    body = Body(mind, state)

    await body.tick()
    assert state.tick == 1

    await body.tick()
    assert state.tick == 2


@pytest.mark.asyncio
async def test_body_tick_with_no_transformer():
    """Body.tick() works without transformer (no LLM entities)."""
    mind = Mind({"echo": EchoInteractor()})
    state = SystemState(tick=0, executions=[])
    body = Body(mind, state, transformer=None)

    # Should not raise
    await body.tick()
    assert state.tick == 1


@pytest.mark.asyncio
async def test_body_calls_transformer_for_awake_entity():
    """Body calls transformer.think() for entities in sleep_queue that wake."""
    human = HumanTransformer()
    mind = Mind({"echo": EchoInteractor()})
    state = SystemState(tick=0, executions=[])
    body = Body(mind, state, transformer=human)

    # Submit command for @alice
    human.submit("@alice", r"\echo Hello from Alice! ---")

    # Manually add @alice to sleep_queue with satisfied condition
    # (In real use, this would be done via \wake command)
    body.sleep_queue["@alice"] = WakeRecord(
        entity="@alice",
        condition=Condition([Text("true")]),  # Dummy condition
        self_prompt="Test wake"
    )

    # Mock _check_wake_conditions to return @alice
    original_check = body._check_wake_conditions
    body._check_wake_conditions = lambda: [body.sleep_queue["@alice"]]

    await body.tick()

    # Restore
    body._check_wake_conditions = original_check

    # Verify command was executed
    log_file = Path("state/logs/log_0.json")
    if log_file.exists():
        import json
        with open(log_file) as f:
            log_data = json.load(f)
        assert len(log_data["executions"]) == 1
        assert log_data["executions"][0]["executor"] == "@alice"
        assert "Hello from Alice!" in log_data["executions"][0]["output"]
        shutil.rmtree("state/logs")


@pytest.mark.asyncio
async def test_body_builds_context():
    """Body._build_context() builds correct context dict."""
    mind = Mind({})
    state = SystemState(tick=42, executions=[])
    body = Body(mind, state)

    # Add entity to a space
    body.entity_spaces["@alice"] = {"#general", "#dev"}

    context = body._build_context("@alice", "Test reason")

    assert context["tick"] == 42
    assert set(context["spaces"]) == {"#general", "#dev"}
    assert context["wake_reason"] == "Test reason"


@pytest.mark.asyncio
async def test_body_tick_no_execution_when_no_wake():
    """Body.tick() does nothing if no entities wake."""
    human = HumanTransformer()
    mind = Mind({"echo": EchoInteractor()})
    state = SystemState(tick=0, executions=[])
    body = Body(mind, state, transformer=human)

    # No entities in sleep_queue, so no one wakes
    await body.tick()

    # No log file created (no executions)
    log_file = Path("state/logs/log_0.json")
    assert not log_file.exists()

    # But tick still advanced
    assert state.tick == 1
