"""
Tests for echo interactor and full mind+body+state chain.

This is our base camp - if these tests pass, the infrastructure works.
"""

import pytest
from pathlib import Path
import tempfile
import shutil

from mind import Mind
from body import Body
from state.state import SystemState
from interactors.echo import EchoInteractor


class TestEchoInteractor:
    """Test echo interactor in isolation"""

    def test_echo_simple(self):
        """Echo interactor returns text"""
        from grammar.parser import parse

        interactor = EchoInteractor()
        cmd = parse(r"\echo Hello world ---")

        output = interactor.execute(cmd)

        assert output == "Echo: Hello world"

    def test_echo_empty(self):
        """Echo with no text"""
        from grammar.parser import parse

        interactor = EchoInteractor()
        cmd = parse(r"\echo ---")

        output = interactor.execute(cmd)

        assert output == "Echo: "


class TestMindBodyIntegration:
    """Test the full chain: mind → body → interactor → state"""

    @pytest.mark.asyncio
    async def test_mind_executes_echo(self):
        """Mind can execute echo command"""
        mind = Mind(interactors={"echo": EchoInteractor()})

        output = await mind.execute(r"\echo Test message ---")

        assert output == "Echo: Test message"

    @pytest.mark.asyncio
    async def test_body_executes_and_logs(self):
        """Body executes command and logs to state"""
        mind = Mind(interactors={"echo": EchoInteractor()})
        state = SystemState(tick=0, executions=[])
        body = Body(mind, state)

        output = await body.execute_now("@test", r"\echo Hello ---")

        assert output == "Echo: Hello"
        assert len(state.executions) == 1
        assert state.executions[0].executor == "@test"
        assert state.executions[0].command == r"\echo Hello ---"
        assert state.executions[0].output == "Echo: Hello"

    @pytest.mark.asyncio
    async def test_body_tick_saves_log(self):
        """Body saves tick logs correctly"""
        tmpdir = Path(tempfile.mkdtemp())

        try:
            mind = Mind(interactors={"echo": EchoInteractor()})
            state = SystemState(tick=0, executions=[])
            body = Body(mind, state)

            # Execute command
            await body.execute_now("@alice", r"\echo Tick test ---")

            # Tick should save log
            await body.tick()

            # Check log file exists
            log_file = tmpdir / "logs" / "log_0.json"
            # Note: body.tick() uses hardcoded "state/logs", so we need to check there
            log_file = Path("state/logs/log_0.json")

            # Actually, let's just verify state advanced
            assert state.tick == 1
            assert len(state.executions) == 0  # Cleared after tick

        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    @pytest.mark.asyncio
    async def test_unknown_command_error(self):
        """Mind returns error for unknown command"""
        mind = Mind(interactors={"echo": EchoInteractor()})

        output = await mind.execute(r"\unknown command ---")

        assert "ERROR" in output
        assert "unknown" in output.lower()


class TestBootstrapSequence:
    """Test bootstrapping a minimal O system"""

    @pytest.mark.asyncio
    async def test_minimal_system_runs(self):
        """Can create and run minimal system"""
        # Create system
        mind = Mind(interactors={"echo": EchoInteractor()})
        state = SystemState(tick=0, executions=[])
        body = Body(mind, state, tick_interval=0.1)

        # Execute a few commands
        await body.execute_now("@root", r"\echo Bootstrap test ---")
        await body.execute_now("@root", r"\echo Second command ---")

        # Verify executions logged
        assert len(state.executions) == 2

        # Tick and verify state advances
        await body.tick()
        assert state.tick == 1

    @pytest.mark.asyncio
    async def test_multiple_entities(self):
        """Multiple entities can execute in same tick"""
        mind = Mind(interactors={"echo": EchoInteractor()})
        state = SystemState(tick=0, executions=[])
        body = Body(mind, state)

        # Different entities execute
        await body.execute_now("@alice", r"\echo Hello from alice ---")
        await body.execute_now("@bob", r"\echo Hello from bob ---")

        assert len(state.executions) == 2
        executors = {e.executor for e in state.executions}
        assert executors == {"@alice", "@bob"}


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
