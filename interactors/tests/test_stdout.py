"""Tests for stdout interactor"""

import pytest
from pathlib import Path
import shutil
from grammar.parser import parse
from interactors.stdout import StdoutInteractor
from body import Body
from mind import Mind
from state.state import SystemState


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
def mock_body():
    """Create mock body with state"""
    state = SystemState(tick=42, executions=[])
    mind = Mind(interactors={})
    body = Body(mind, state)
    return body


def test_stdout_write_basic(test_memory_dir, mock_body):
    """Test basic write functionality"""
    stdout = StdoutInteractor(body=mock_body, memory_root=str(test_memory_dir))

    cmd = parse("\\stdout write: Hello from test ---")
    result = stdout.execute(cmd, executor="@alice")

    assert "Written to stdout" in result
    assert "tick 42" in result

    # Verify file was created
    stdout_file = test_memory_dir / "@alice.jsonl"
    assert stdout_file.exists()

    # Verify content
    with open(stdout_file, "r") as f:
        lines = f.readlines()
        assert len(lines) == 1
        import json
        entry = json.loads(lines[0])
        assert entry["entity"] == "@alice"
        assert entry["content"] == "Hello from test"
        assert entry["tick"] == 42


def test_stdout_write_multiple(test_memory_dir, mock_body):
    """Test multiple writes append"""
    stdout = StdoutInteractor(body=mock_body, memory_root=str(test_memory_dir))

    cmd1 = parse("\\stdout write: First entry ---")
    cmd2 = parse("\\stdout write: Second entry ---")

    stdout.execute(cmd1, executor="@alice")
    stdout.execute(cmd2, executor="@alice")

    stdout_file = test_memory_dir / "@alice.jsonl"
    with open(stdout_file, "r") as f:
        lines = f.readlines()
        assert len(lines) == 2


def test_stdout_read_empty(test_memory_dir, mock_body):
    """Test reading when no stdout exists"""
    stdout = StdoutInteractor(body=mock_body, memory_root=str(test_memory_dir))

    cmd = parse("\\stdout read: last 10 ---")
    result = stdout.execute(cmd, executor="@alice")

    assert "No stdout for @alice yet" in result


def test_stdout_read_last_n(test_memory_dir, mock_body):
    """Test reading last N entries"""
    stdout = StdoutInteractor(body=mock_body, memory_root=str(test_memory_dir))

    # Write 5 entries
    for i in range(5):
        cmd = parse(f"\\stdout write: Entry {i} ---")
        stdout.execute(cmd, executor="@alice")

    # Read last 3
    cmd = parse("\\stdout read: last 3 ---")
    result = stdout.execute(cmd, executor="@alice")

    assert "Last 3 stdout entries" in result
    assert "Entry 2" in result
    assert "Entry 3" in result
    assert "Entry 4" in result
    assert "Entry 0" not in result  # Should not include earlier entries


def test_stdout_read_default(test_memory_dir, mock_body):
    """Test read with no params defaults to last 1"""
    stdout = StdoutInteractor(body=mock_body, memory_root=str(test_memory_dir))

    # Write 15 entries
    for i in range(15):
        cmd = parse(f"\\stdout write: Entry {i} ---")
        stdout.execute(cmd, executor="@alice")

    # Read without params (should get last 1)
    cmd = parse("\\stdout read: ---")
    result = stdout.execute(cmd, executor="@alice")

    assert "Last 1 stdout entries" in result
    assert "Entry 14" in result  # Most recent
    assert "Entry 13" not in result  # Not included


def test_stdout_implicit_write(test_memory_dir, mock_body):
    """Test that content without write keyword is treated as write"""
    stdout = StdoutInteractor(body=mock_body, memory_root=str(test_memory_dir))

    # No "write:" keyword
    cmd = parse("\\stdout Just writing something ---")
    result = stdout.execute(cmd, executor="@alice")

    assert "Written to stdout" in result

    # Verify it was written
    stdout_file = test_memory_dir / "@alice.jsonl"
    assert stdout_file.exists()


def test_stdout_requires_executor(test_memory_dir, mock_body):
    """Test that stdout requires executor context"""
    stdout = StdoutInteractor(body=mock_body, memory_root=str(test_memory_dir))

    cmd = parse("\\stdout write: Test ---")
    result = stdout.execute(cmd, executor=None)

    assert "ERROR" in result
    assert "executor" in result.lower()


def test_stdout_empty_write(test_memory_dir, mock_body):
    """Test writing empty content fails"""
    stdout = StdoutInteractor(body=mock_body, memory_root=str(test_memory_dir))

    cmd = parse("\\stdout write: ---")
    result = stdout.execute(cmd, executor="@alice")

    assert "ERROR" in result
    assert "No content" in result


def test_stdout_help_general(test_memory_dir, mock_body):
    """Test general help output"""
    stdout = StdoutInteractor(body=mock_body, memory_root=str(test_memory_dir))

    cmd = parse("\\stdout help: ---")
    result = stdout.execute(cmd, executor="@alice")

    assert "\\stdout - Memory persistence layer" in result
    assert "write:" in result
    assert "read:" in result
    assert "help:" in result
    assert "Quick start" in result


def test_stdout_help_write(test_memory_dir, mock_body):
    """Test help for write operation"""
    stdout = StdoutInteractor(body=mock_body, memory_root=str(test_memory_dir))

    cmd = parse("\\stdout help: write ---")
    result = stdout.execute(cmd, executor="@alice")

    assert "write: Persist a log entry" in result
    assert "Usage:" in result
    assert "Examples:" in result
    assert "JSONL" in result


def test_stdout_help_read(test_memory_dir, mock_body):
    """Test help for read operation"""
    stdout = StdoutInteractor(body=mock_body, memory_root=str(test_memory_dir))

    cmd = parse("\\stdout help: read ---")
    result = stdout.execute(cmd, executor="@alice")

    assert "read: Query your stdout history" in result
    assert "last N" in result
    assert "defaults to last 1" in result
    assert "per-entity storage" in result.lower()


def test_stdout_help_between(test_memory_dir, mock_body):
    """Test help for between operation"""
    stdout = StdoutInteractor(body=mock_body, memory_root=str(test_memory_dir))

    cmd = parse("\\stdout help: between ---")
    result = stdout.execute(cmd, executor="@alice")

    assert "between: Query temporal range" in result
    assert "TICK_START TICK_END" in result
    assert "Use cases:" in result


def test_stdout_help_query(test_memory_dir, mock_body):
    """Test help for query operation"""
    stdout = StdoutInteractor(body=mock_body, memory_root=str(test_memory_dir))

    cmd = parse("\\stdout help: query ---")
    result = stdout.execute(cmd, executor="@alice")

    assert "query: Search entries" in result
    assert "substring match" in result
    assert "Use cases:" in result


def test_stdout_between_basic(test_memory_dir, mock_body):
    """Test basic between functionality"""
    stdout = StdoutInteractor(body=mock_body, memory_root=str(test_memory_dir))

    # Write entries at different ticks
    for i in range(10):
        mock_body.state.tick = i * 10  # Ticks: 0, 10, 20, 30, ..., 90
        cmd = parse(f"\\stdout write: Entry at tick {i*10} ---")
        stdout.execute(cmd, executor="@alice")

    # Query between tick 20 and 50
    cmd = parse("\\stdout between: 20 50 ---")
    result = stdout.execute(cmd, executor="@alice")

    assert "Entries between tick 20 and 50" in result
    assert "Entry at tick 20" in result
    assert "Entry at tick 30" in result
    assert "Entry at tick 40" in result
    assert "Entry at tick 50" in result
    assert "Entry at tick 10" not in result  # Before range
    assert "Entry at tick 60" not in result  # After range


def test_stdout_between_natural_language(test_memory_dir, mock_body):
    """Test between with 'and' keyword"""
    stdout = StdoutInteractor(body=mock_body, memory_root=str(test_memory_dir))

    for i in range(5):
        mock_body.state.tick = i
        cmd = parse(f"\\stdout write: Entry {i} ---")
        stdout.execute(cmd, executor="@alice")

    # Natural language: "1 and 3"
    cmd = parse("\\stdout between: 1 and 3 ---")
    result = stdout.execute(cmd, executor="@alice")

    assert "Entry 1" in result
    assert "Entry 2" in result
    assert "Entry 3" in result
    assert "Entry 0" not in result
    assert "Entry 4" not in result


def test_stdout_between_single_tick(test_memory_dir, mock_body):
    """Test querying exact single tick"""
    stdout = StdoutInteractor(body=mock_body, memory_root=str(test_memory_dir))

    for i in range(5):
        mock_body.state.tick = i
        cmd = parse(f"\\stdout write: Entry {i} ---")
        stdout.execute(cmd, executor="@alice")

    # Query exactly tick 2
    cmd = parse("\\stdout between: 2 2 ---")
    result = stdout.execute(cmd, executor="@alice")

    assert "Entry 2" in result
    assert "Entry 1" not in result
    assert "Entry 3" not in result


def test_stdout_between_empty_range(test_memory_dir, mock_body):
    """Test between with no matches"""
    stdout = StdoutInteractor(body=mock_body, memory_root=str(test_memory_dir))

    mock_body.state.tick = 1
    cmd = parse("\\stdout write: Only entry ---")
    stdout.execute(cmd, executor="@alice")

    # Query range with no entries
    cmd = parse("\\stdout between: 10 20 ---")
    result = stdout.execute(cmd, executor="@alice")

    assert "No entries between tick 10 and 20" in result


def test_stdout_between_invalid_range(test_memory_dir, mock_body):
    """Test between with start > end"""
    stdout = StdoutInteractor(body=mock_body, memory_root=str(test_memory_dir))

    cmd = parse("\\stdout between: 50 20 ---")
    result = stdout.execute(cmd, executor="@alice")

    assert "ERROR" in result
    assert "must be <=" in result


def test_stdout_between_invalid_params(test_memory_dir, mock_body):
    """Test between with invalid parameters"""
    stdout = StdoutInteractor(body=mock_body, memory_root=str(test_memory_dir))

    # Not enough params
    cmd = parse("\\stdout between: 10 ---")
    result = stdout.execute(cmd, executor="@alice")
    assert "ERROR" in result
    assert "Invalid between params" in result

    # Non-integer params
    cmd = parse("\\stdout between: abc def ---")
    result = stdout.execute(cmd, executor="@alice")
    assert "ERROR" in result
    assert "must be integers" in result


def test_stdout_query_basic(test_memory_dir, mock_body):
    """Test basic query functionality"""
    stdout = StdoutInteractor(body=mock_body, memory_root=str(test_memory_dir))

    # Write various entries
    messages = [
        "Task started successfully",
        "ERROR: Connection failed",
        "Processing 10 items",
        "ERROR: Invalid input",
        "Task completed",
        "Mentioned @bob in conversation"
    ]

    for i, msg in enumerate(messages):
        mock_body.state.tick = i
        cmd = parse(f"\\stdout write: {msg} ---")
        stdout.execute(cmd, executor="@alice")

    # Query for errors
    cmd = parse("\\stdout query: error ---")
    result = stdout.execute(cmd, executor="@alice")

    assert "Entries matching 'error'" in result
    assert "Connection failed" in result
    assert "Invalid input" in result
    assert "Task started" not in result  # No match
    assert "Processing" not in result


def test_stdout_query_case_insensitive(test_memory_dir, mock_body):
    """Test query is case-insensitive"""
    stdout = StdoutInteractor(body=mock_body, memory_root=str(test_memory_dir))

    cmd = parse("\\stdout write: ERROR in system ---")
    stdout.execute(cmd, executor="@alice")

    # Query with lowercase
    cmd = parse("\\stdout query: error ---")
    result = stdout.execute(cmd, executor="@alice")

    assert "ERROR in system" in result


def test_stdout_query_entity_mention(test_memory_dir, mock_body):
    """Test querying for entity mentions"""
    stdout = StdoutInteractor(body=mock_body, memory_root=str(test_memory_dir))

    messages = [
        "Talked to @alice about task",
        "Waiting for @bob response",
        "@alice and @bob both agreed",
        "Solo work today"
    ]

    for msg in messages:
        cmd = parse(f"\\stdout write: {msg} ---")
        stdout.execute(cmd, executor="@charlie")

    # Query for @bob mentions
    cmd = parse("\\stdout query: @bob ---")
    result = stdout.execute(cmd, executor="@charlie")

    assert "Waiting for @bob response" in result
    assert "@alice and @bob both agreed" in result
    assert "Talked to @alice about task" not in result
    assert "Solo work" not in result


def test_stdout_query_no_matches(test_memory_dir, mock_body):
    """Test query with no results"""
    stdout = StdoutInteractor(body=mock_body, memory_root=str(test_memory_dir))

    cmd = parse("\\stdout write: Normal operation ---")
    stdout.execute(cmd, executor="@alice")

    cmd = parse("\\stdout query: error ---")
    result = stdout.execute(cmd, executor="@alice")

    assert "No entries matching 'error'" in result


def test_stdout_query_empty_pattern(test_memory_dir, mock_body):
    """Test query with no pattern"""
    stdout = StdoutInteractor(body=mock_body, memory_root=str(test_memory_dir))

    cmd = parse("\\stdout query: ---")
    result = stdout.execute(cmd, executor="@alice")

    assert "ERROR" in result
    assert "No query pattern" in result
