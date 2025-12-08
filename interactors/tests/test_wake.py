"""Tests for wake interactor."""

import pytest
from interactors.wake import WakeInteractor
from grammar.parser import parse
from mind import Mind
from body import Body, WakeRecord
from state.state import SystemState


def test_wake_requires_executor():
    """Wake needs to know who is sleeping."""
    wake = WakeInteractor()
    cmd = parse(r"\wake ?(response(@bob)) Check messages ---")

    result = wake.execute(cmd, executor=None)
    assert "ERROR" in result
    assert "requires executor" in result


def test_wake_requires_condition():
    """Wake needs a condition."""
    wake = WakeInteractor()
    cmd = parse(r"\wake No condition here ---")

    result = wake.execute(cmd, executor="@alice")
    assert "ERROR" in result
    assert "No condition" in result


def test_wake_without_body_returns_guard():
    """Wake without body shows what it would do."""
    wake = WakeInteractor()  # No body connected
    cmd = parse(r"\wake ?(response(@bob)) Check messages ---")

    result = wake.execute(cmd, executor="@alice")
    assert "Would register wake" in result
    assert "@alice" in result


def test_wake_registers_with_body():
    """Wake registers condition in body.sleep_queue."""
    mind = Mind({})
    state = SystemState(tick=0, executions=[])
    body = Body(mind, state)

    wake = WakeInteractor(body=body)
    cmd = parse(r"\wake ?(response(@bob)) Check what Bob said ---")

    result = wake.execute(cmd, executor="@alice")

    # Verify success message
    assert "Registered wake condition" in result
    assert "Check what Bob said" in result

    # Verify added to sleep queue
    assert "@alice" in body.sleep_queue

    # Verify wake record structure
    record = body.sleep_queue["@alice"]
    assert record.entity == "@alice"
    assert record.condition is not None
    assert record.self_prompt == "Check what Bob said"
    assert record.resume_command is None


def test_wake_without_prompt():
    """Wake can have condition without self-prompt."""
    mind = Mind({})
    state = SystemState(tick=0, executions=[])
    body = Body(mind, state)

    wake = WakeInteractor(body=body)
    cmd = parse(r"\wake ?(sleep(10)) ---")

    result = wake.execute(cmd, executor="@alice")

    assert "Registered wake condition" in result

    # Verify in sleep queue with no prompt
    record = body.sleep_queue["@alice"]
    assert record.entity == "@alice"
    assert record.self_prompt is None


@pytest.mark.asyncio
async def test_wake_via_body_execute():
    """Wake through full Body.execute_now() flow."""
    wake = WakeInteractor()
    mind = Mind({"wake": wake})
    state = SystemState(tick=0, executions=[])
    body = Body(mind, state)

    # Connect wake to body
    wake.body = body

    # Execute wake command
    result = await body.execute_now("@alice", r"\wake ?(response(@bob)) Test prompt ---")

    assert "Registered wake condition" in result

    # Verify state
    assert "@alice" in body.sleep_queue
    assert len(state.executions) == 1
    assert state.executions[0].executor == "@alice"


def test_wake_overwrites_previous_condition():
    """Calling wake twice updates the condition."""
    mind = Mind({})
    state = SystemState(tick=0, executions=[])
    body = Body(mind, state)

    wake = WakeInteractor(body=body)

    # First wake
    cmd1 = parse(r"\wake ?(sleep(5)) First prompt ---")
    wake.execute(cmd1, executor="@alice")

    # Second wake (overwrites)
    cmd2 = parse(r"\wake ?(response(@bob)) Second prompt ---")
    wake.execute(cmd2, executor="@alice")

    # Should have second condition
    record = body.sleep_queue["@alice"]
    assert record.self_prompt == "Second prompt"


def test_wake_multiple_entities():
    """Multiple entities can register wake conditions."""
    mind = Mind({})
    state = SystemState(tick=0, executions=[])
    body = Body(mind, state)

    wake = WakeInteractor(body=body)

    # Alice wakes on Bob's response
    cmd1 = parse(r"\wake ?(response(@bob)) Alice waiting ---")
    wake.execute(cmd1, executor="@alice")

    # Bob wakes on sleep timer
    cmd2 = parse(r"\wake ?(sleep(10)) Bob timer ---")
    wake.execute(cmd2, executor="@bob")

    # Both in sleep queue
    assert "@alice" in body.sleep_queue
    assert "@bob" in body.sleep_queue
    assert body.sleep_queue["@alice"].self_prompt == "Alice waiting"
    assert body.sleep_queue["@bob"].self_prompt == "Bob timer"
