"""
Tests for O state system.

Tests the four primitives: tick, executor, command, output
"""

import pytest
from pathlib import Path
import sys
import tempfile
import shutil

sys.path.append(str(Path(__file__).parent.parent.parent))

from state.state import ExecutionRecord, SystemState
from grammar.parser import parse, Command


class TestExecutionRecord:
    """Test the primitive execution record"""

    def test_create_execution_record(self):
        """Can create a basic execution record"""
        record = ExecutionRecord(
            executor="@bob",
            command=r"\say @alice Hello ---",
            output="Message sent"
        )

        assert record.executor == "@bob"
        assert record.command == r"\say @alice Hello ---"
        assert record.output == "Message sent"
        # Can parse command when needed
        assert isinstance(record.get_command(), Command)

    def test_serialize_execution_record(self):
        """Can serialize execution record to dict"""
        record = ExecutionRecord(
            executor="@alice",
            command=r"\status ---",
            output="Entity: @alice\nBudget: 42"
        )

        data = record.to_dict()

        assert data["executor"] == "@alice"
        assert data["command"] == r"\status ---"
        assert data["output"] == "Entity: @alice\nBudget: 42"


class TestSystemState:
    """Test system state management"""

    def test_create_empty_state(self):
        """Can create a new system state"""
        state = SystemState(tick=0, executions=[])
        assert state.tick == 0
        assert len(state.executions) == 0

    def test_add_execution(self):
        """Can add executions to state"""
        state = SystemState(tick=1, executions=[])

        state.add_execution(
            executor="@alice",
            command=r"\say #general Hello ---",
            output="Posted to #general"
        )

        assert len(state.executions) == 1
        assert state.executions[0].executor == "@alice"

    def test_advance_tick(self):
        """Can advance to next tick"""
        state = SystemState(tick=1, executions=[])
        state.add_execution("@alice", r"\status ---", "Status output")

        state.advance_tick()

        assert state.tick == 2
        assert len(state.executions) == 0  # Buffer cleared

    def test_save_and_load_state(self):
        """Can save and load state.json"""
        tmpdir = Path(tempfile.mkdtemp())

        try:
            state = SystemState(tick=5, executions=[])
            state.add_execution("@alice", r"\say @bob Test ---", "Message sent")

            state_path = tmpdir / "state.json"
            state.save_state(state_path)

            loaded = SystemState.load_state(state_path)

            assert loaded.tick == 5
            assert len(loaded.executions) == 1
            assert loaded.executions[0].executor == "@alice"

        finally:
            shutil.rmtree(tmpdir)

    def test_save_tick_log(self):
        """Can save tick logs"""
        tmpdir = Path(tempfile.mkdtemp())

        try:
            state = SystemState(tick=10, executions=[])

            state.add_execution("@alice", r"\say #general Morning ---", "Posted")
            state.add_execution("@bob", r"\spawn @worker ---", "Spawned @worker")

            log_dir = tmpdir / "logs"
            state.save_tick_log(log_dir)

            log_path = log_dir / "log_10.json"
            assert log_path.exists()

            tick, logs = SystemState.load_tick_log(log_path)
            assert tick == 10
            assert len(logs) == 2

        finally:
            shutil.rmtree(tmpdir)


class TestLogReconstruction:
    """Test that reconstruction is possible by scanning logs"""

    def test_filter_by_entity(self):
        """Can filter execution records by entity"""
        records = [
            ExecutionRecord("@alice", r"\say Hi ---", ""),
            ExecutionRecord("@bob", r"\say Bye ---", ""),
            ExecutionRecord("@alice", r"\status ---", "")
        ]

        # Simple list comprehension - no utility function needed
        alice_records = [r for r in records if r.executor == "@alice"]

        assert len(alice_records) == 2
        assert all(r.executor == "@alice" for r in alice_records)


class TestTheFourBehaviors:
    """
    Test that the four logical behaviors (Closed, Open, DepthLimit, Split)
    emerge from the execution records without explicit status fields.
    """

    def test_closed_behavior(self):
        """Closed = command completed, no wake condition"""
        record = ExecutionRecord(
            executor="@alice",
            command=r"\say #general Done ---",
            output="Posted to #general"
        )

        # Closed behavior: no 'wake' in command, output shows success
        assert "wake" not in record.command
        assert record.output != ""  # Has output = completed

    def test_open_behavior(self):
        """Open = command set wake condition"""
        record = ExecutionRecord(
            executor="@alice",
            command=r"\wake ?(response(@bob)) ---",
            output="Wake condition set: response(@bob)"
        )

        # Open behavior: contains wake command with Condition
        from grammar.parser import Condition
        cmd = record.get_command()
        has_condition = any(
            isinstance(node, Condition)
            for node in cmd.content
        )
        assert has_condition

    def test_depth_limit_behavior(self):
        """DepthLimit = budget exhausted (in output/error)"""
        record = ExecutionRecord(
            executor="@alice",
            command=r"\say #general Working ---",
            output="ERROR: Budget exhausted"
        )

        # DepthLimit behavior: error message indicates resource limit
        assert "Budget exhausted" in record.output

    def test_split_behavior(self):
        """Split = spawned multiple entities"""
        record = ExecutionRecord(
            executor="@root",
            command=r"\spawn @(worker1, worker2) ---",
            output="Spawned: @worker1, @worker2"
        )

        # Split behavior: spawn command with multiple entities
        from grammar.parser import Entity
        cmd = record.get_command()
        entities = [
            n for n in cmd.content
            if isinstance(n, Entity)
        ]
        assert len(entities) > 1  # Multiple entities = split


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
