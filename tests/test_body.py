"""
Comprehensive tests for Body (the environment substrate).

Body is the physics - it should:
- Maintain the cyclical structure (spaces ↔ entities)
- Tick autonomously
- Execute commands and log to state
- Manage sleep queue
- Be autonomous but controllable
"""

import pytest
from pathlib import Path
import tempfile
import shutil

from body import Body, Space, WakeRecord
from mind import Mind
from state.state import SystemState
from grammar.parser import Condition, parse
from interactors.echo import EchoInteractor
from interactors.name import NameInteractor


class TestBodyInitialization:
    """Test Body initialization"""

    def test_body_initializes_empty(self):
        """Body starts with empty substrate"""
        mind = Mind(interactors={})
        state = SystemState(tick=0, executions=[])
        body = Body(mind, state)

        assert len(body.spaces) == 0
        assert len(body.entity_spaces) == 0
        assert len(body.sleep_queue) == 0

    def test_body_stores_references(self):
        """Body stores mind and state references"""
        mind = Mind(interactors={})
        state = SystemState(tick=0, executions=[])
        body = Body(mind, state)

        assert body.mind is mind
        assert body.state is state

    def test_body_sets_tick_interval(self):
        """Body respects tick_interval parameter"""
        mind = Mind(interactors={})
        state = SystemState(tick=0, executions=[])
        body = Body(mind, state, tick_interval=2.5)

        assert body.tick_interval == 2.5


class TestSpatialSubstrate:
    """Test the cyclical structure (spaces ↔ entities)"""

    def test_spaces_can_be_added(self):
        """Spaces can be added to body.spaces"""
        mind = Mind(interactors={})
        state = SystemState(tick=0, executions=[])
        body = Body(mind, state)

        body.spaces["#test"] = Space(name="#test", members={"@alice"})

        assert "#test" in body.spaces
        assert "@alice" in body.spaces["#test"].members

    def test_entity_spaces_can_be_added(self):
        """Entity memberships can be tracked"""
        mind = Mind(interactors={})
        state = SystemState(tick=0, executions=[])
        body = Body(mind, state)

        body.entity_spaces["@alice"] = {"#test", "#work"}

        assert "@alice" in body.entity_spaces
        assert "#test" in body.entity_spaces["@alice"]
        assert "#work" in body.entity_spaces["@alice"]

    def test_bidirectional_edges(self):
        """Spaces and entities form bidirectional graph"""
        mind = Mind(interactors={})
        state = SystemState(tick=0, executions=[])
        body = Body(mind, state)

        # Add space → entity edge
        body.spaces["#family"] = Space(name="#family", members={"@alice", "@bob"})

        # Add entity → space edges
        body.entity_spaces["@alice"] = {"#family"}
        body.entity_spaces["@bob"] = {"#family"}

        # Verify bidirectional
        assert "@alice" in body.spaces["#family"].members
        assert "#family" in body.entity_spaces["@alice"]


class TestExecuteNow:
    """Test immediate execution (bypassing temporal layer)"""

    @pytest.mark.asyncio
    async def test_execute_now_runs_command(self):
        """execute_now executes command immediately"""
        mind = Mind(interactors={"echo": EchoInteractor()})
        state = SystemState(tick=0, executions=[])
        body = Body(mind, state)

        output = await body.execute_now("@alice", r"\echo Hello ---")

        assert output == "Echo: Hello"

    @pytest.mark.asyncio
    async def test_execute_now_logs_to_state(self):
        """execute_now adds execution to state"""
        mind = Mind(interactors={"echo": EchoInteractor()})
        state = SystemState(tick=0, executions=[])
        body = Body(mind, state)

        await body.execute_now("@alice", r"\echo Test ---")

        assert len(state.executions) == 1
        assert state.executions[0].executor == "@alice"
        assert state.executions[0].command == r"\echo Test ---"
        assert state.executions[0].output == "Echo: Test"

    @pytest.mark.asyncio
    async def test_execute_now_passes_executor(self):
        """execute_now passes executor to mind"""
        mind = Mind(interactors={"echo": EchoInteractor()})
        state = SystemState(tick=0, executions=[])
        body = Body(mind, state)

        await body.execute_now("@bob", r"\echo Hi ---")

        assert state.executions[0].executor == "@bob"

    @pytest.mark.asyncio
    async def test_execute_now_multiple_commands(self):
        """execute_now can be called multiple times"""
        mind = Mind(interactors={"echo": EchoInteractor()})
        state = SystemState(tick=0, executions=[])
        body = Body(mind, state)

        await body.execute_now("@alice", r"\echo First ---")
        await body.execute_now("@bob", r"\echo Second ---")
        await body.execute_now("@charlie", r"\echo Third ---")

        assert len(state.executions) == 3
        assert state.executions[0].executor == "@alice"
        assert state.executions[1].executor == "@bob"
        assert state.executions[2].executor == "@charlie"


class TestTick:
    """Test the tick mechanism"""

    @pytest.mark.asyncio
    async def test_tick_advances_state(self):
        """Tick advances state.tick"""
        mind = Mind(interactors={})
        state = SystemState(tick=0, executions=[])
        body = Body(mind, state)

        await body.tick()

        assert state.tick == 1

    @pytest.mark.asyncio
    async def test_tick_clears_executions(self):
        """Tick clears execution buffer"""
        mind = Mind(interactors={"echo": EchoInteractor()})
        state = SystemState(tick=0, executions=[])
        body = Body(mind, state)

        await body.execute_now("@alice", r"\echo Test ---")
        assert len(state.executions) == 1

        await body.tick()

        assert len(state.executions) == 0

    @pytest.mark.asyncio
    async def test_tick_saves_log(self):
        """Tick saves execution log to disk"""
        tmpdir = Path(tempfile.mkdtemp())

        try:
            mind = Mind(interactors={"echo": EchoInteractor()})
            state = SystemState(tick=0, executions=[])
            body = Body(mind, state)

            await body.execute_now("@alice", r"\echo Test ---")
            await body.tick()

            # Check log file exists
            log_file = Path("state/logs/log_0.json")
            assert log_file.exists()

        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)
            # Clean up created logs
            if Path("state/logs").exists():
                shutil.rmtree("state/logs", ignore_errors=True)

    @pytest.mark.asyncio
    async def test_tick_preserves_body_state(self):
        """Tick doesn't clear body.spaces or entity_spaces"""
        mind = Mind(interactors={"name": NameInteractor(body=None)})
        state = SystemState(tick=0, executions=[])
        body = Body(mind, state)

        # Connect interactor to body
        mind.interactors["name"].body = body

        # Create space
        await body.execute_now("@root", r"\name #family @(alice, bob) ---")
        assert "#family" in body.spaces

        # Tick should not clear body state
        await body.tick()

        assert "#family" in body.spaces
        assert body.spaces["#family"].members == {"@alice", "@bob"}

    @pytest.mark.asyncio
    async def test_multiple_ticks(self):
        """Multiple ticks work correctly"""
        mind = Mind(interactors={"echo": EchoInteractor()})
        state = SystemState(tick=0, executions=[])
        body = Body(mind, state)

        await body.tick()
        await body.tick()
        await body.tick()

        assert state.tick == 3


class TestSleepQueue:
    """Test sleep queue (temporal coordination)"""

    def test_sleep_queue_can_be_modified(self):
        """Sleep queue can have records added"""
        mind = Mind(interactors={})
        state = SystemState(tick=0, executions=[])
        body = Body(mind, state)

        # Create a simple condition
        condition = parse(r"\name #test @alice ---").content[0]  # Just use any node

        body.sleep_queue["@alice"] = WakeRecord(
            entity="@alice",
            condition=condition,
            self_prompt="Test prompt"
        )

        assert "@alice" in body.sleep_queue
        assert body.sleep_queue["@alice"].self_prompt == "Test prompt"

    def test_sleep_queue_can_be_removed(self):
        """Records can be removed from sleep queue"""
        mind = Mind(interactors={})
        state = SystemState(tick=0, executions=[])
        body = Body(mind, state)

        condition = parse(r"\name #test @alice ---").content[0]
        body.sleep_queue["@alice"] = WakeRecord(
            entity="@alice",
            condition=condition
        )

        del body.sleep_queue["@alice"]

        assert "@alice" not in body.sleep_queue


class TestBodyWithNameInteractor:
    """Test Body working with NameInteractor"""

    @pytest.mark.asyncio
    async def test_naming_updates_spatial_substrate(self):
        """NameInteractor modifies body.spaces"""
        mind = Mind(interactors={"name": NameInteractor(body=None)})
        state = SystemState(tick=0, executions=[])
        body = Body(mind, state)

        mind.interactors["name"].body = body

        await body.execute_now("@root", r"\name #dev @(alice, bob, charlie) ---")

        assert "#dev" in body.spaces
        assert body.spaces["#dev"].members == {"@alice", "@bob", "@charlie"}
        assert "@alice" in body.entity_spaces
        assert "#dev" in body.entity_spaces["@alice"]

    @pytest.mark.asyncio
    async def test_multiple_namings(self):
        """Multiple naming operations work"""
        mind = Mind(interactors={"name": NameInteractor(body=None)})
        state = SystemState(tick=0, executions=[])
        body = Body(mind, state)

        mind.interactors["name"].body = body

        await body.execute_now("@root", r"\name #dev @(alice, bob) ---")
        await body.execute_now("@root", r"\name #design @(bob, charlie) ---")

        assert "#dev" in body.spaces
        assert "#design" in body.spaces
        assert "@bob" in body.entity_spaces
        assert "#dev" in body.entity_spaces["@bob"]
        assert "#design" in body.entity_spaces["@bob"]


class TestAutonomousOperation:
    """Test autonomous run() method"""

    @pytest.mark.asyncio
    async def test_run_stops_at_max_ticks(self):
        """run() stops after max_ticks"""
        mind = Mind(interactors={})
        state = SystemState(tick=0, executions=[])
        body = Body(mind, state, tick_interval=0.001)  # Fast ticks

        await body.run(max_ticks=5)

        assert state.tick == 5

    @pytest.mark.asyncio
    async def test_run_executes_multiple_ticks(self):
        """run() executes multiple ticks"""
        mind = Mind(interactors={"echo": EchoInteractor()})
        state = SystemState(tick=0, executions=[])
        body = Body(mind, state, tick_interval=0.001)

        await body.execute_now("@alice", r"\echo Test ---")
        await body.run(max_ticks=3)

        # Tick 0: saves log with 1 execution
        # Ticks 1-2: no executions
        assert state.tick == 3


class TestEdgeCases:
    """Test edge cases and error conditions"""

    @pytest.mark.asyncio
    async def test_execute_now_with_invalid_command(self):
        """execute_now handles invalid commands"""
        mind = Mind(interactors={})
        state = SystemState(tick=0, executions=[])
        body = Body(mind, state)

        output = await body.execute_now("@alice", r"\unknown test ---")

        assert "ERROR" in output

    @pytest.mark.asyncio
    async def test_tick_with_no_executions(self):
        """Tick works when no executions occurred"""
        mind = Mind(interactors={})
        state = SystemState(tick=0, executions=[])
        body = Body(mind, state)

        await body.tick()

        assert state.tick == 1
        assert len(state.executions) == 0

    @pytest.mark.asyncio
    async def test_body_with_empty_mind(self):
        """Body works with mind that has no interactors"""
        mind = Mind(interactors={})
        state = SystemState(tick=0, executions=[])
        body = Body(mind, state)

        output = await body.execute_now("@test", r"\anything ---")

        assert "ERROR" in output


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
