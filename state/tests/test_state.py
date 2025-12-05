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
        cmd = parse(r"\say @alice Hello ---")
        record = ExecutionRecord(
            tick=1,
            executor="@bob",
            command=cmd,
            output="Message sent"
        )

        assert record.tick == 1
        assert record.executor == "@bob"
        assert isinstance(record.command, Command)
        assert record.output == "Message sent"

    def test_serialize_execution_record(self):
        """Can serialize execution record to dict"""
        cmd = parse(r"\status ---")
        record = ExecutionRecord(
            tick=5,
            executor="@alice",
            command=cmd,
            output="Entity: @alice\nBudget: 42"
        )

        data = record.to_dict()

        assert data["tick"] == 5
        assert data["executor"] == "@alice"
        assert "command" in data
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
        cmd = parse(r"\say #general Hello ---")

        state.add_execution(
            executor="@alice",
            command=cmd,
            output="Posted to #general"
        )

        assert len(state.executions) == 1
        assert state.executions[0].tick == 1
        assert state.executions[0].executor == "@alice"

    def test_advance_tick(self):
        """Can advance to next tick"""
        state = SystemState(tick=1, executions=[])
        cmd = parse(r"\status ---")
        state.add_execution("@alice", cmd, "Status output")

        state.advance_tick()

        assert state.tick == 2
        assert len(state.executions) == 0  # Buffer cleared

    def test_save_and_load_state(self):
        """Can save and load state.json"""
        tmpdir = Path(tempfile.mkdtemp())

        try:
            state = SystemState(tick=5, executions=[])
            cmd = parse(r"\say @bob Test ---")
            state.add_execution("@alice", cmd, "Message sent")

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
            cmd1 = parse(r"\say #general Morning ---")
            cmd2 = parse(r"\spawn @worker ---")

            state.add_execution("@alice", cmd1, "Posted")
            state.add_execution("@bob", cmd2, "Spawned @worker")

            log_dir = tmpdir / "logs"
            state.save_tick_log(log_dir)

            log_path = log_dir / "log_10.json"
            assert log_path.exists()

            logs = SystemState.load_tick_log(log_path)
            assert len(logs) == 2

        finally:
            shutil.rmtree(tmpdir)


class TestLogReconstruction:
    """Test deriving information from execution logs"""

    def test_reconstruct_entity_executions(self):
        """Can filter logs by entity"""
        from state.state import reconstruct_entity_executions

        records = [
            ExecutionRecord(1, "@alice", parse(r"\say Hi ---"), ""),
            ExecutionRecord(1, "@bob", parse(r"\say Bye ---"), ""),
            ExecutionRecord(2, "@alice", parse(r"\status ---"), "")
        ]

        alice_records = reconstruct_entity_executions(records, "@alice")

        assert len(alice_records) == 2
        assert all(r.executor == "@alice" for r in alice_records)

    def test_find_wake_conditions(self):
        """Can extract wake conditions from logs"""
        from state.state import find_wake_conditions

        records = [
            ExecutionRecord(
                1,
                "@alice",
                parse(r"\wake ?(sleep(30)) ---"),
                "Wake condition set"
            ),
            ExecutionRecord(
                2,
                "@bob",
                parse(r"\say Hi ---"),
                "Message sent"
            )
        ]

        wake_conds = find_wake_conditions(records)

        assert "@alice" in wake_conds
        assert "@bob" not in wake_conds

    def test_count_spawns(self):
        """Can count spawned entities from logs"""
        from state.state import count_spawns

        records = [
            ExecutionRecord(
                1,
                "@root",
                parse(r"\spawn @worker-1 ---"),
                "Spawned @worker-1"
            ),
            ExecutionRecord(
                2,
                "@root",
                parse(r"\spawn @(alice, bob, charlie) ---"),
                "Spawned 3 entities"
            )
        ]

        count = count_spawns(records)
        assert count == 4  # 1 + 3


class TestTheFourBehaviors:
    """
    Test that the four logical behaviors (Closed, Open, DepthLimit, Split)
    emerge from the execution records without explicit status fields.
    """

    def test_closed_behavior(self):
        """Closed = command completed, no wake condition"""
        record = ExecutionRecord(
            tick=1,
            executor="@alice",
            command=parse(r"\say #general Done ---"),
            output="Posted to #general"
        )

        # Closed behavior: no 'wake' in command, output shows success
        assert "wake" not in str(record.command)
        assert record.output != ""  # Has output = completed

    def test_open_behavior(self):
        """Open = command set wake condition"""
        record = ExecutionRecord(
            tick=1,
            executor="@alice",
            command=parse(r"\wake ?(response(@bob)) ---"),
            output="Wake condition set: response(@bob)"
        )

        # Open behavior: contains wake command with Condition
        from grammar.parser import Condition
        has_condition = any(
            isinstance(node, Condition)
            for node in record.command.content
        )
        assert has_condition

    def test_depth_limit_behavior(self):
        """DepthLimit = budget exhausted (in output/error)"""
        record = ExecutionRecord(
            tick=1,
            executor="@alice",
            command=parse(r"\say #general Working ---"),
            output="ERROR: Budget exhausted"
        )

        # DepthLimit behavior: error message indicates resource limit
        assert "Budget exhausted" in record.output

    def test_split_behavior(self):
        """Split = spawned multiple entities"""
        record = ExecutionRecord(
            tick=1,
            executor="@root",
            command=parse(r"\spawn @(worker1, worker2) ---"),
            output="Spawned: @worker1, @worker2"
        )

        # Split behavior: spawn command with multiple entities
        from grammar.parser import Entity
        entities = [
            n for n in record.command.content
            if isinstance(n, Entity)
        ]
        assert len(entities) > 1  # Multiple entities = split


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
