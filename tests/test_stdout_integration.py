"""Integration tests for stdout interactor with Body/Mind/State"""

import pytest
from pathlib import Path
import shutil
from mind import Mind
from body import Body
from state.state import SystemState
from interactors.stdout import StdoutInteractor


@pytest.fixture
def test_memory_dir(tmp_path):
    """Create temporary memory directory"""
    memory_dir = tmp_path / "memory" / "stdout"
    memory_dir.mkdir(parents=True)
    yield memory_dir
    # Cleanup
    if memory_dir.parent.exists():
        shutil.rmtree(memory_dir.parent)


@pytest.fixture
def integrated_system(test_memory_dir):
    """Create fully integrated Mind-Body-State system with stdout"""
    state = SystemState(tick=0, executions=[])

    # Create stdout interactor
    stdout = StdoutInteractor(memory_root=str(test_memory_dir))

    # Create mind with stdout
    mind = Mind(interactors={"stdout": stdout})

    # Create body and give it the mind
    body = Body(mind, state)

    # Connect stdout to body (for tick access)
    stdout.body = body

    return body


def test_stdout_write_via_body(integrated_system):
    """Test writing to stdout through body.execute_now"""
    body = integrated_system

    # Execute stdout write
    result = body.execute_now("@alice", r"\stdout write: Test message ---")

    assert "Written to stdout" in result
    assert "tick 0" in result

    # Verify execution was logged
    assert len(body.state.executions) == 1
    assert body.state.executions[0].executor == "@alice"
    assert "stdout write: Test message" in body.state.executions[0].command


def test_stdout_read_via_body(integrated_system):
    """Test reading stdout through body.execute_now"""
    body = integrated_system

    # Write multiple entries across ticks
    body.execute_now("@alice", r"\stdout write: Entry 1 ---")
    body.tick()  # Advance to tick 1

    body.execute_now("@alice", r"\stdout write: Entry 2 ---")
    body.tick()  # Advance to tick 2

    body.execute_now("@alice", r"\stdout write: Entry 3 ---")

    # Read last 2 entries
    result = body.execute_now("@alice", r"\stdout read: last 2 ---")

    assert "Last 2 stdout entries" in result
    assert "Entry 2" in result
    assert "Entry 3" in result
    assert "Entry 1" not in result


def test_stdout_between_across_ticks(integrated_system):
    """Test between query across multiple ticks"""
    body = integrated_system

    # Write entries at different ticks
    for i in range(5):
        body.execute_now("@alice", f"\\stdout write: Tick {i} activity ---")
        body.tick()

    # Query entries between tick 1 and 3
    result = body.execute_now("@alice", r"\stdout between: 1 and 3 ---")

    assert "Entries between tick 1 and 3" in result
    assert "Tick 1 activity" in result
    assert "Tick 2 activity" in result
    assert "Tick 3 activity" in result
    assert "Tick 0 activity" not in result
    assert "Tick 4 activity" not in result


def test_stdout_query_integration(integrated_system):
    """Test query with real execution flow"""
    body = integrated_system

    # Simulate entity logging various activities
    messages = [
        "Started processing task A",
        "ERROR: Failed to connect to @bob",
        "Retrying connection",
        "ERROR: Timeout after 30s",
        "Completed task A"
    ]

    for msg in messages:
        body.execute_now("@alice", f"\\stdout write: {msg} ---")
        body.tick()

    # Query for errors
    result = body.execute_now("@alice", r"\stdout query: error ---")

    assert "Entries matching 'error'" in result
    assert "Failed to connect" in result
    assert "Timeout" in result
    assert "Completed task A" not in result


def test_stdout_help_integration(integrated_system):
    """Test help through integrated system"""
    body = integrated_system

    result = body.execute_now("@alice", r"\stdout help: ---")

    assert "\\stdout - Memory persistence layer" in result
    assert "Operations:" in result
    assert "write:" in result
    assert "read:" in result
    assert "between:" in result
    assert "query:" in result


def test_multiple_entities_isolated_stdout(integrated_system):
    """Test that different entities have isolated stdout"""
    body = integrated_system

    # Alice writes
    body.execute_now("@alice", r"\stdout write: Alice's first entry ---")
    body.execute_now("@alice", r"\stdout write: Alice's second entry ---")

    # Bob writes
    body.execute_now("@bob", r"\stdout write: Bob's first entry ---")

    # Alice reads only her own stdout
    result = body.execute_now("@alice", r"\stdout read: last 10 ---")

    assert "Alice's first entry" in result
    assert "Alice's second entry" in result
    assert "Bob's first entry" not in result  # Isolated!

    # Bob reads only his own stdout
    result = body.execute_now("@bob", r"\stdout read: last 10 ---")

    assert "Bob's first entry" in result
    assert "Alice's first entry" not in result  # Isolated!


def test_stdout_persists_across_ticks(integrated_system):
    """Test that stdout persists across tick boundaries"""
    body = integrated_system

    # Write at tick 0
    body.execute_now("@alice", r"\stdout write: Tick 0 entry ---")
    assert body.state.tick == 0

    # Advance many ticks
    for _ in range(10):
        body.tick()

    assert body.state.tick == 10

    # Write at tick 10
    body.execute_now("@alice", r"\stdout write: Tick 10 entry ---")

    # Read should show both entries
    result = body.execute_now("@alice", r"\stdout read: last 10 ---")

    assert "Tick 0 entry" in result
    assert "Tick 10 entry" in result


def test_implicit_write_integration(integrated_system):
    """Test implicit write (no 'write:' keyword) through body"""
    body = integrated_system

    # Implicit write
    result = body.execute_now("@alice", r"\stdout Just a quick note ---")

    assert "Written to stdout" in result

    # Verify it was actually written
    read_result = body.execute_now("@alice", r"\stdout read: ---")
    assert "Just a quick note" in read_result
