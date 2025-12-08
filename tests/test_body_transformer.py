"""Test Body tick() with new transformer interface (list_entities, read_command, write_output)."""

import pytest
from transformers.human import HumanTransformer
from mind import Mind
from body import Body
from state.state import SystemState
from interactors.echo import EchoInteractor
from interactors.stdout import StdoutInteractor
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
    """Body.tick() works without transformer (no external I/O)."""
    mind = Mind({"echo": EchoInteractor()})
    state = SystemState(tick=0, executions=[])
    body = Body(mind, state, transformer=None)

    # Should not raise
    await body.tick()
    assert state.tick == 1


@pytest.mark.asyncio
async def test_body_polls_transformer_for_commands():
    """Body polls transformer for commands from entities."""
    human = HumanTransformer()
    mind = Mind({"echo": EchoInteractor()})
    state = SystemState(tick=0, executions=[])
    body = Body(mind, state, transformer=human)

    # Submit command for @alice
    human.submit("@alice", r"\echo Hello from Alice! ---")

    await body.tick()

    # Verify command was executed
    assert len(state.executions) == 0  # Cleared by advance_tick

    # Check output was written back
    outputs = human.get_outputs("@alice")
    assert len(outputs) == 1
    assert "Hello from Alice" in outputs[0]["output"]


@pytest.mark.asyncio
async def test_body_executes_multiple_entities():
    """Body executes commands from multiple entities in one tick."""
    human = HumanTransformer()
    mind = Mind({"echo": EchoInteractor()})
    state = SystemState(tick=0, executions=[])
    body = Body(mind, state, transformer=human)

    # Submit commands for two entities
    human.submit("@alice", r"\echo Hello from Alice ---")
    human.submit("@bob", r"\echo Hello from Bob ---")

    await body.tick()

    # Both should have outputs
    alice_outputs = human.get_outputs("@alice")
    bob_outputs = human.get_outputs("@bob")

    assert len(alice_outputs) == 1
    assert len(bob_outputs) == 1
    assert "Alice" in alice_outputs[0]["output"]
    assert "Bob" in bob_outputs[0]["output"]


@pytest.mark.asyncio
async def test_body_tick_no_execution_when_no_pending():
    """Body.tick() does nothing if no commands pending."""
    human = HumanTransformer()
    mind = Mind({"echo": EchoInteractor()})
    state = SystemState(tick=0, executions=[])
    body = Body(mind, state, transformer=human)

    # No commands submitted
    await body.tick()

    # No outputs written (no commands executed)
    assert human.get_outputs("@alice") == []
    assert human.get_outputs("@bob") == []

    # But tick still advanced
    assert state.tick == 1


@pytest.mark.asyncio
async def test_body_writes_output_with_tick():
    """Body writes output with current tick."""
    human = HumanTransformer()
    mind = Mind({"echo": EchoInteractor()})
    state = SystemState(tick=42, executions=[])
    body = Body(mind, state, transformer=human)

    human.submit("@alice", r"\echo Test ---")

    await body.tick()

    outputs = human.get_outputs("@alice")
    assert outputs[0]["tick"] == 42
