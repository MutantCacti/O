"""Tests for transformer (I/O device) polling."""

import pytest
from transformers.base import Transformer
from transformers.human import HumanTransformer
from mind import Mind
from body import Body
from state.state import SystemState
from interactors.echo import EchoInteractor


def test_transformer_base_is_abstract():
    """Transformer is abstract - cannot instantiate directly."""
    with pytest.raises(TypeError):
        Transformer()


def test_human_transformer_polls_empty():
    """HumanTransformer returns None when no input."""
    body = Body(Mind({}), SystemState(tick=0, executions=[]))
    human = HumanTransformer()

    result = human.poll(body)
    assert result is None


def test_human_transformer_polls_input():
    """HumanTransformer returns input when available."""
    body = Body(Mind({}), SystemState(tick=0, executions=[]))
    human = HumanTransformer()

    # Submit input
    human.submit("@alice", r"\echo test ---")

    # Poll returns it
    result = human.poll(body)
    assert result == ("@alice", r"\echo test ---")

    # Second poll returns None (consumed)
    result = human.poll(body)
    assert result is None


def test_body_polls_transformer():
    """Body can poll transformer and execute command."""
    mind = Mind({"echo": EchoInteractor()})
    state = SystemState(tick=0, executions=[])
    body = Body(mind, state)

    human = HumanTransformer()
    human.submit("@alice", r"\echo Hello! ---")

    # Poll transformer
    result = human.poll(body)
    assert result is not None

    entity, command = result

    # Execute command
    output = body.execute_now(entity, command)
    assert "Hello!" in output

    # Verify execution logged
    assert len(state.executions) == 1
    assert state.executions[0].executor == "@alice"
