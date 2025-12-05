"""
Tests for name interactor - The first magic.

When O learns to Name, it gains the power to create relational addresses.
These tests prove the magic works.
"""

import pytest
from pathlib import Path

from mind import Mind
from body import Body, Space
from state.state import SystemState
from interactors.name import NameInteractor


class TestNameInteractor:
    """Test the naming magic in isolation"""

    def test_name_creates_space(self):
        """Naming brings a space into being"""
        from grammar.parser import parse

        # Create the infrastructure
        state = SystemState(tick=0, executions=[])
        body = Body(Mind(interactors={}), state)
        interactor = NameInteractor(body=body)

        # Execute the naming
        cmd = parse(r"\name #family @alice ---")
        output = interactor.execute(cmd, executor="@root")

        # Verify the space was created
        assert "#family" in body.spaces
        assert body.spaces["#family"].name == "#family"
        assert "@alice" in body.spaces["#family"].members

    def test_name_creates_bidirectional_edges(self):
        """Naming creates Space→Entity and Entity→Space edges"""
        from grammar.parser import parse

        state = SystemState(tick=0, executions=[])
        body = Body(Mind(interactors={}), state)
        interactor = NameInteractor(body=body)

        # Name a space with multiple entities
        cmd = parse(r"\name #family @(alice, bob, charlie) ---")
        output = interactor.execute(cmd, executor="@root")

        # Verify Space → Entities (forward edge)
        assert "#family" in body.spaces
        assert body.spaces["#family"].members == {"@alice", "@bob", "@charlie"}

        # Verify Entity → Spaces (reverse edges)
        assert "@alice" in body.entity_spaces
        assert "#family" in body.entity_spaces["@alice"]

        assert "@bob" in body.entity_spaces
        assert "#family" in body.entity_spaces["@bob"]

        assert "@charlie" in body.entity_spaces
        assert "#family" in body.entity_spaces["@charlie"]

    def test_name_multiple_spaces_same_entity(self):
        """One entity can be in multiple spaces"""
        from grammar.parser import parse

        state = SystemState(tick=0, executions=[])
        body = Body(Mind(interactors={}), state)
        interactor = NameInteractor(body=body)

        # Create multiple spaces including same entity
        interactor.execute(parse(r"\name #family @(alice, bob) ---"))
        interactor.execute(parse(r"\name #work @(alice, charlie) ---"))

        # Verify alice is in both spaces
        assert "@alice" in body.entity_spaces
        assert "#family" in body.entity_spaces["@alice"]
        assert "#work" in body.entity_spaces["@alice"]

        # Verify spaces have correct members
        assert body.spaces["#family"].members == {"@alice", "@bob"}
        assert body.spaces["#work"].members == {"@alice", "@charlie"}

    def test_name_overwrites_existing_space(self):
        """Re-naming a space updates its members"""
        from grammar.parser import parse

        state = SystemState(tick=0, executions=[])
        body = Body(Mind(interactors={}), state)
        interactor = NameInteractor(body=body)

        # Create initial space
        interactor.execute(parse(r"\name #family @(alice, bob) ---"))
        assert body.spaces["#family"].members == {"@alice", "@bob"}

        # Re-name with different members
        interactor.execute(parse(r"\name #family @(charlie, dave) ---"))
        assert body.spaces["#family"].members == {"@charlie", "@dave"}

        # Old members still have the space in their entity_spaces
        # (This might be a design decision - should old edges be removed?)
        # For now, we're testing current behavior

    def test_name_error_no_space(self):
        """Error when no space specified"""
        from grammar.parser import parse

        state = SystemState(tick=0, executions=[])
        body = Body(Mind(interactors={}), state)
        interactor = NameInteractor(body=body)

        # Command with no space
        cmd = parse(r"\name @alice ---")
        output = interactor.execute(cmd)

        assert "ERROR" in output
        assert "No space specified" in output

    def test_name_error_no_entities(self):
        """Error when no entities specified"""
        from grammar.parser import parse

        state = SystemState(tick=0, executions=[])
        body = Body(Mind(interactors={}), state)
        interactor = NameInteractor(body=body)

        # Command with no entities
        cmd = parse(r"\name #family ---")
        output = interactor.execute(cmd)

        assert "ERROR" in output
        assert "No entities specified" in output


class TestNameIntegration:
    """Test name interactor through Mind→Body→State chain"""

    def test_name_via_mind(self):
        """Naming works through the full execution chain"""
        state = SystemState(tick=0, executions=[])
        body = Body(None, state)  # Mind set later

        # Create mind with name interactor
        mind = Mind(interactors={"name": NameInteractor(body=body)})
        body.mind = mind

        # Execute via body.execute_now
        output = body.execute_now("@root", r"\name #general @(alice, bob, charlie) ---")

        # Verify output
        assert "Named #general" in output
        assert "alice" in output

        # Verify state logged it
        assert len(state.executions) == 1
        assert state.executions[0].executor == "@root"
        assert state.executions[0].command == r"\name #general @(alice, bob, charlie) ---"
        assert "Named #general" in state.executions[0].output

        # Verify body state updated
        assert "#general" in body.spaces
        assert body.spaces["#general"].members == {"@alice", "@bob", "@charlie"}

    def test_name_multiple_via_body(self):
        """Multiple naming commands work in sequence"""
        state = SystemState(tick=0, executions=[])
        body = Body(None, state)

        mind = Mind(interactors={"name": NameInteractor(body=body)})
        body.mind = mind

        # Execute multiple naming commands
        body.execute_now("@root", r"\name #dev @(alice, bob) ---")
        body.execute_now("@root", r"\name #design @(bob, charlie) ---")

        # Verify both spaces exist
        assert "#dev" in body.spaces
        assert "#design" in body.spaces

        # Verify bob is in both
        assert "@bob" in body.entity_spaces
        assert "#dev" in body.entity_spaces["@bob"]
        assert "#design" in body.entity_spaces["@bob"]

        # Verify state logged both
        assert len(state.executions) == 2

    def test_name_and_tick(self):
        """Naming commands persist through tick"""
        state = SystemState(tick=0, executions=[])
        body = Body(None, state)

        mind = Mind(interactors={"name": NameInteractor(body=body)})
        body.mind = mind

        # Execute naming
        body.execute_now("@root", r"\name #family @(alice, bob) ---")

        # Verify pre-tick state
        assert "#family" in body.spaces
        assert len(state.executions) == 1

        # Tick (saves log and advances)
        body.tick()

        # Verify post-tick state
        assert state.tick == 1
        assert len(state.executions) == 0  # Buffer cleared

        # Verify body state persists (not cleared by tick)
        assert "#family" in body.spaces
        assert body.spaces["#family"].members == {"@alice", "@bob"}


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
