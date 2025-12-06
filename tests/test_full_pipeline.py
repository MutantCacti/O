"""
Full pipeline integration tests: Mind + Body + State + Name + Stdout

Tests the complete flow of entities using multiple interactors together.
"""

import pytest
from pathlib import Path
import shutil
from mind import Mind
from body import Body
from state.state import SystemState
from interactors.name import NameInteractor
from interactors.stdout import StdoutInteractor


@pytest.fixture
def test_memory_dir(tmp_path):
    """Create temporary memory directory"""
    memory_dir = tmp_path / "memory" / "stdout"
    memory_dir.mkdir(parents=True)
    yield memory_dir
    if memory_dir.parent.exists():
        shutil.rmtree(memory_dir.parent)


@pytest.fixture
def full_system(test_memory_dir):
    """Create fully integrated system with multiple interactors"""
    state = SystemState(tick=0, executions=[])

    # Create both interactors
    name_int = NameInteractor()
    stdout_int = StdoutInteractor(memory_root=str(test_memory_dir))

    # Create mind with both interactors
    mind = Mind(interactors={
        "name": name_int,
        "stdout": stdout_int
    })

    # Create body and connect everything
    body = Body(mind, state)
    name_int.body = body
    stdout_int.body = body

    return body


class TestBasicPipeline:
    """Test basic command execution through the full pipeline"""

    def test_single_command_flow(self, full_system):
        """Test one command flows through: Mind → parse → execute → Body → State"""
        body = full_system

        # Execute command
        result = body.execute_now("@alice", r"\stdout write: Hello from alice ---")

        # Verify mind executed it
        assert "Written to stdout" in result

        # Verify state logged it
        assert len(body.state.executions) == 1
        assert body.state.executions[0].executor == "@alice"

        # Verify stdout persisted it
        read_result = body.execute_now("@alice", r"\stdout read: ---")
        assert "Hello from alice" in read_result


class TestMultipleInteractors:
    """Test multiple interactors working together"""

    def test_name_then_stdout(self, full_system):
        """Use \name to create space, then \stdout to log it"""
        body = full_system

        # Create a named space
        name_result = body.execute_now("@alice", r"\name #team @(alice, bob, charlie) ---")
        assert "Named #team" in name_result

        # Log the creation
        body.execute_now("@alice", r"\stdout Created #team with @bob and @charlie ---")

        # Verify space exists
        assert "#team" in body.spaces
        assert "@alice" in body.spaces["#team"].members

        # Verify logged
        read_result = body.execute_now("@alice", r"\stdout read: ---")
        assert "Created #team" in read_result


class TestMultipleEntities:
    """Test multiple entities interacting through the system"""

    def test_two_entities_separate_stdout(self, full_system):
        """Two entities use stdout independently"""
        body = full_system

        # Alice writes (use brackets, not colons)
        body.execute_now("@alice", r"\stdout [Alice] Starting task A ---")
        body.tick()

        # Bob writes
        body.execute_now("@bob", r"\stdout [Bob] Starting task B ---")
        body.tick()

        # Alice writes again
        body.execute_now("@alice", r"\stdout [Alice] Completed task A ---")

        # Verify isolation
        alice_log = body.execute_now("@alice", r"\stdout read: last 10 ---")
        assert "Starting task A" in alice_log
        assert "Completed task A" in alice_log
        assert "Bob" not in alice_log

        bob_log = body.execute_now("@bob", r"\stdout read: last 10 ---")
        assert "Starting task B" in bob_log
        assert "Alice" not in bob_log

    def test_entities_collaborate_via_spaces(self, full_system):
        """Entities use \name to collaborate, log with \stdout"""
        body = full_system

        # Alice creates project space
        body.execute_now("@alice", r"\name #project-x @(alice, bob) ---")
        body.execute_now("@alice", r"\stdout Initialized #project-x with @bob ---")

        # Bob acknowledges joining
        body.execute_now("@bob", r"\stdout Joined #project-x, working with @alice ---")
        body.tick()

        # Alice checks her history
        alice_log = body.execute_now("@alice", r"\stdout query: project-x ---")
        assert "Initialized #project-x" in alice_log

        # Bob checks his history
        bob_log = body.execute_now("@bob", r"\stdout query: project-x ---")
        assert "Joined #project-x" in bob_log

        # Verify space exists with both members
        assert "@alice" in body.spaces["#project-x"].members
        assert "@bob" in body.spaces["#project-x"].members


class TestTemporalBehavior:
    """Test behavior across tick boundaries"""

    def test_stdout_persists_across_ticks(self, full_system):
        """Stdout entries persist as ticks advance"""
        body = full_system

        # Write at tick 0
        body.execute_now("@alice", r"\stdout [tick 0] System initialized ---")
        assert body.state.tick == 0

        # Advance several ticks
        for i in range(1, 5):
            body.tick()
            body.execute_now("@alice", f"\\stdout [tick {i}] Processed batch {i} ---")

        assert body.state.tick == 4  # Started at 0, ticked 4 times

        # Query specific range
        result = body.execute_now("@alice", r"\stdout between: 1 and 3 ---")
        assert "[tick 1]" in result
        assert "[tick 2]" in result
        assert "[tick 3]" in result
        assert "[tick 0]" not in result
        assert "[tick 4]" not in result

    def test_state_reconstruction_scenario(self, full_system):
        """Simulate entity waking up and reconstructing state"""
        body = full_system

        # Entity does work and logs it
        body.execute_now("@worker", r"\name #task-queue @worker ---")
        body.execute_now("@worker", r"\stdout Started working on #task-queue ---")
        body.tick()

        body.execute_now("@worker", r"\stdout Processed item 1 from #task-queue ---")
        body.tick()

        body.execute_now("@worker", r"\stdout Processed item 2 from #task-queue ---")
        body.tick()

        # Entity "sleeps" (many ticks pass)
        for _ in range(10):
            body.tick()

        # Entity "wakes" and needs to remember what it was doing
        # Step 1: What was I doing?
        recent = body.execute_now("@worker", r"\stdout read: last 5 ---")
        assert "task-queue" in recent

        # Step 2: Where am I?
        assert "@worker" in body.entity_spaces
        assert "#task-queue" in body.entity_spaces["@worker"]

        # Step 3: Continue work
        body.execute_now("@worker", r"\stdout Resumed work after sleep ---")

        # Verify continuity
        full_log = body.execute_now("@worker", r"\stdout read: last 10 ---")
        assert "Started working" in full_log
        assert "Resumed work" in full_log


class TestErrorHandling:
    """Test error conditions across the pipeline"""

    def test_invalid_interactor_logged(self, full_system):
        """Unknown interactor returns error through pipeline"""
        body = full_system

        result = body.execute_now("@alice", r"\unknown command here ---")

        assert "ERROR" in result
        assert "Unknown command 'unknown'" in result

        # Execution still logged even though it failed
        assert len(body.state.executions) == 1
        assert "ERROR" in body.state.executions[0].output

    def test_interactor_error_logged(self, full_system):
        """Interactor error flows back through pipeline"""
        body = full_system

        result = body.execute_now("@alice", r"\stdout find: something ---")

        assert "ERROR" in result
        assert "Unknown operation" in result

        # Error logged in state
        assert len(body.state.executions) == 1
        assert "ERROR" in body.state.executions[0].output


class TestComplexWorkflows:
    """Test realistic complex workflows"""

    def test_multi_entity_project_workflow(self, full_system):
        """Simulate a multi-entity project workflow"""
        body = full_system

        # --- Tick 0: Project initialization ---
        body.execute_now("@lead", r"\name #backend-team @(lead, dev1, dev2) ---")
        body.execute_now("@lead", r"\stdout [INIT] Created #backend-team ---")

        # --- Tick 1: Team members join and log ---
        body.tick()
        body.execute_now("@dev1", r"\stdout [JOIN] Joined #backend-team ---")
        body.execute_now("@dev2", r"\stdout [JOIN] Joined #backend-team ---")

        # --- Tick 2: Work begins ---
        body.tick()
        body.execute_now("@lead", r"\stdout [TASK] Assigned parser work to @dev1 ---")
        body.execute_now("@dev1", r"\stdout [WORK] Starting on parser module ---")

        # --- Tick 3: Progress updates ---
        body.tick()
        body.execute_now("@dev1", r"\stdout [PROGRESS] Parser 50% complete ---")
        body.execute_now("@dev2", r"\stdout [WORK] Starting on tests ---")

        # --- Tick 4: Completion ---
        body.tick()
        body.execute_now("@dev1", r"\stdout [DONE] Parser completed ---")
        body.execute_now("@dev2", r"\stdout [DONE] Tests written ---")

        # --- Verification ---
        # Team structure exists
        assert len(body.spaces["#backend-team"].members) == 3

        # Lead can query team activity
        lead_view = body.execute_now("@lead", r"\stdout query: backend-team ---")
        assert "Created #backend-team" in lead_view

        # Dev1 can see their work history
        dev1_history = body.execute_now("@dev1", r"\stdout read: last 10 ---")
        assert "Starting on parser" in dev1_history
        assert "Parser completed" in dev1_history

        # Can query specific time range
        early_work = body.execute_now("@dev1", r"\stdout between: 1 and 2 ---")
        assert "JOIN" in early_work
        assert "Starting on parser" in early_work
        assert "DONE" not in early_work  # Completed later

    def test_entity_handoff_scenario(self, full_system):
        """One entity hands off work to another"""
        body = full_system

        # Alice starts work
        body.execute_now("@alice", r"\name #urgent-task @alice ---")
        body.execute_now("@alice", r"\stdout Started urgent task, need help ---")
        body.tick()

        # Alice brings in Bob
        body.execute_now("@alice", r"\name #urgent-task @(alice, bob) ---")
        body.execute_now("@alice", r"\stdout Added @bob to #urgent-task ---")
        body.tick()

        # Bob picks up
        body.execute_now("@bob", r"\stdout Picking up #urgent-task from @alice ---")
        body.tick()

        # Alice documents handoff
        body.execute_now("@alice", r"\stdout Handed off #urgent-task to @bob ---")

        # Both can see their involvement
        alice_log = body.execute_now("@alice", r"\stdout query: urgent-task ---")
        # Note: content includes "stdout" prefix from full_text reconstruction
        assert "urgent-task" in alice_log
        assert "Added @bob" in alice_log or "Handed off" in alice_log

        bob_log = body.execute_now("@bob", r"\stdout query: urgent-task ---")
        assert "Picking up #urgent-task" in bob_log

        # Space has both members
        assert "@alice" in body.spaces["#urgent-task"].members
        assert "@bob" in body.spaces["#urgent-task"].members


class TestEdgeCases:
    """Test edge cases and boundary conditions"""

    def test_same_space_renamed_multiple_times(self, full_system):
        """Renaming space multiple times, logging each change"""
        body = full_system

        # Initial creation
        body.execute_now("@owner", r"\name #project @owner ---")
        body.execute_now("@owner", r"\stdout Created #project ---")
        body.tick()

        # Add member
        body.execute_now("@owner", r"\name #project @(owner, member1) ---")
        body.execute_now("@owner", r"\stdout Added @member1 to #project ---")
        body.tick()

        # Add another member
        body.execute_now("@owner", r"\name #project @(owner, member1, member2) ---")
        body.execute_now("@owner", r"\stdout Added @member2 to #project ---")

        # Verify final state
        assert len(body.spaces["#project"].members) == 3

        # Verify history shows evolution
        history = body.execute_now("@owner", r"\stdout read: last 10 ---")
        assert "Created #project" in history
        assert "Added @member1" in history
        assert "Added @member2" in history

    def test_high_volume_logging(self, full_system):
        """Many log entries, verify query performance"""
        body = full_system

        # Write 100 entries
        for i in range(100):
            body.execute_now("@worker", f"\\stdout Entry {i} ---")
            if i % 10 == 0:
                body.tick()

        # Query recent
        recent = body.execute_now("@worker", r"\stdout read: last 5 ---")
        assert "Entry 99" in recent
        assert "Entry 95" in recent

        # Query specific range
        mid_range = body.execute_now("@worker", r"\stdout between: 3 and 5 ---")
        assert "Entry" in mid_range

        # Query pattern
        tens = body.execute_now("@worker", r"\stdout query: Entry 1 ---")
        # Should match "Entry 1", "Entry 10", "Entry 11", etc.
        assert "Entry 1" in tens


class TestStatePersistence:
    """Test that state persists correctly through tick()"""

    def test_tick_preserves_spaces_and_stdout(self, full_system):
        """After tick(), spaces and stdout should persist"""
        body = full_system

        # Setup state at tick 0
        body.execute_now("@alice", r"\name #persistent @alice ---")
        body.execute_now("@alice", r"\stdout Created at tick 0 ---")

        # Tick and verify persistence
        body.tick()
        assert body.state.tick == 1
        assert "#persistent" in body.spaces

        # Stdout should still be readable
        result = body.execute_now("@alice", r"\stdout read: last 10 ---")
        assert "Created at tick 0" in result

        # Write at new tick
        body.execute_now("@alice", r"\stdout Now at tick 1 ---")

        # Both entries should be present
        full_history = body.execute_now("@alice", r"\stdout read: last 10 ---")
        assert "tick 0" in full_history
        assert "tick 1" in full_history
