"""Tests for say interactor."""

import json
import pytest
from pathlib import Path
from grammar.parser import parse
from interactors.say import SayInteractor


@pytest.fixture
def tmp_spaces(tmp_path):
    """Create temporary spaces directory."""
    spaces_dir = tmp_path / "spaces"
    spaces_dir.mkdir()
    return spaces_dir


@pytest.fixture
def say(tmp_spaces):
    """Create say interactor with temp directory."""
    return SayInteractor(spaces_root=str(tmp_spaces))


def test_say_requires_executor(say):
    """Say requires executor context."""
    cmd = parse(r"\say @bob Hello! ---")
    result = say.execute(cmd)
    assert "ERROR" in result
    assert "executor" in result.lower()


def test_say_requires_target(say):
    """Say requires target entity."""
    cmd = parse(r"\say Hello! ---")
    result = say.execute(cmd, executor="@alice")
    assert "ERROR" in result
    assert "target" in result.lower()


def test_say_requires_message(say):
    """Say requires message content."""
    cmd = parse(r"\say @bob ---")
    result = say.execute(cmd, executor="@alice")
    assert "ERROR" in result
    assert "message" in result.lower()


def test_say_to_single_entity(say, tmp_spaces):
    """Say to single entity creates space with both."""
    cmd = parse(r"\say @bob Hello Bob! ---")
    result = say.execute(cmd, executor="@alice")

    assert "Sent to @alice-@bob" in result

    # Check file created
    space_file = tmp_spaces / "@alice-@bob.jsonl"
    assert space_file.exists()

    # Check content
    with open(space_file) as f:
        entry = json.loads(f.readline())

    assert entry["sender"] == "@alice"
    assert entry["content"] == "Hello Bob!"
    assert entry["tick"] == 0
    assert "timestamp" in entry


def test_say_to_multiple_entities(say, tmp_spaces):
    """Say to multiple entities creates space with all."""
    cmd = parse(r"\say @bob @charlie Hello both! ---")
    result = say.execute(cmd, executor="@alice")

    assert "Sent to @alice-@bob-@charlie" in result

    space_file = tmp_spaces / "@alice-@bob-@charlie.jsonl"
    assert space_file.exists()


def test_say_space_is_sorted(say, tmp_spaces):
    """Space ID is sorted regardless of order in command."""
    cmd = parse(r"\say @charlie @alice Hi! ---")
    result = say.execute(cmd, executor="@bob")

    # Should be sorted: alice, bob, charlie
    assert "Sent to @alice-@bob-@charlie" in result


def test_say_appends_to_existing_space(say, tmp_spaces):
    """Multiple says append to same space file."""
    cmd1 = parse(r"\say @bob First message ---")
    cmd2 = parse(r"\say @alice Second message ---")

    say.execute(cmd1, executor="@alice")
    say.execute(cmd2, executor="@bob")

    space_file = tmp_spaces / "@alice-@bob.jsonl"
    with open(space_file) as f:
        lines = f.readlines()

    assert len(lines) == 2

    entry1 = json.loads(lines[0])
    entry2 = json.loads(lines[1])

    assert entry1["sender"] == "@alice"
    assert entry1["content"] == "First message"
    assert entry2["sender"] == "@bob"
    assert entry2["content"] == "Second message"


def test_say_executor_not_duplicated(say, tmp_spaces):
    """If executor says to themselves, they're not duplicated."""
    cmd = parse(r"\say @alice @bob Note to self and bob ---")
    result = say.execute(cmd, executor="@alice")

    # alice appears once, not twice
    assert "Sent to @alice-@bob" in result


def test_say_with_body_gets_tick(say, tmp_spaces):
    """Say gets tick from body when available."""
    from unittest.mock import Mock

    mock_body = Mock()
    mock_body.state.tick = 42
    mock_body.spaces = {}
    mock_body.entity_spaces = {}
    say.body = mock_body

    cmd = parse(r"\say @bob Hello! ---")
    say.execute(cmd, executor="@alice")

    space_file = tmp_spaces / "@alice-@bob.jsonl"
    with open(space_file) as f:
        entry = json.loads(f.readline())

    assert entry["tick"] == 42


# --- Named space tests ---

def test_say_to_named_space(tmp_spaces):
    """Say to named space writes to space file."""
    from unittest.mock import Mock
    from body import Space as SpaceData

    say = SayInteractor(spaces_root=str(tmp_spaces))

    # Setup body with named space
    mock_body = Mock()
    mock_body.state.tick = 0
    mock_body.spaces = {
        "#general": SpaceData(name="#general", members={"@alice", "@bob", "@charlie"})
    }
    mock_body.entity_spaces = {}
    say.body = mock_body

    cmd = parse(r"\say #general Hello everyone! ---")
    result = say.execute(cmd, executor="@alice")

    assert "Sent to #general" in result

    space_file = tmp_spaces / "#general.jsonl"
    assert space_file.exists()

    with open(space_file) as f:
        entry = json.loads(f.readline())

    assert entry["sender"] == "@alice"
    assert entry["content"] == "Hello everyone!"

    # Verify entity_spaces was updated
    assert "#general" in mock_body.entity_spaces.get("@alice", set())


def test_say_to_named_space_requires_membership(tmp_spaces):
    """Say to named space fails if not a member."""
    from unittest.mock import Mock
    from body import Space as SpaceData

    say = SayInteractor(spaces_root=str(tmp_spaces))

    mock_body = Mock()
    mock_body.state.tick = 0
    mock_body.spaces = {
        "#private": SpaceData(name="#private", members={"@bob", "@charlie"})
    }
    say.body = mock_body

    cmd = parse(r"\say #private Hello! ---")
    result = say.execute(cmd, executor="@alice")

    assert "ERROR" in result
    assert "member" in result.lower()


def test_say_to_nonexistent_space(tmp_spaces):
    """Say to nonexistent space fails."""
    from unittest.mock import Mock

    say = SayInteractor(spaces_root=str(tmp_spaces))

    mock_body = Mock()
    mock_body.state.tick = 0
    mock_body.spaces = {}
    say.body = mock_body

    cmd = parse(r"\say #nowhere Hello! ---")
    result = say.execute(cmd, executor="@alice")

    assert "ERROR" in result
    assert "does not exist" in result


def test_say_to_multiple_spaces(tmp_spaces):
    """Say to multiple named spaces broadcasts to all."""
    from unittest.mock import Mock
    from body import Space as SpaceData

    say = SayInteractor(spaces_root=str(tmp_spaces))

    mock_body = Mock()
    mock_body.state.tick = 0
    mock_body.spaces = {
        "#general": SpaceData(name="#general", members={"@alice", "@bob"}),
        "#dev": SpaceData(name="#dev", members={"@alice", "@charlie"})
    }
    mock_body.entity_spaces = {}
    say.body = mock_body

    cmd = parse(r"\say #general #dev Broadcast! ---")
    result = say.execute(cmd, executor="@alice")

    assert "#general" in result
    assert "#dev" in result

    # Both files created
    assert (tmp_spaces / "#general.jsonl").exists()
    assert (tmp_spaces / "#dev.jsonl").exists()

    # Verify entity_spaces was updated for both
    assert "#general" in mock_body.entity_spaces.get("@alice", set())
    assert "#dev" in mock_body.entity_spaces.get("@alice", set())


def test_say_mixed_entity_and_space(tmp_spaces):
    """Say can target both entities and named spaces."""
    from unittest.mock import Mock
    from body import Space as SpaceData

    say = SayInteractor(spaces_root=str(tmp_spaces))

    mock_body = Mock()
    mock_body.state.tick = 0
    mock_body.spaces = {
        "#general": SpaceData(name="#general", members={"@alice", "@bob"})
    }
    mock_body.entity_spaces = {}
    say.body = mock_body

    cmd = parse(r"\say @charlie #general Hello both places! ---")
    result = say.execute(cmd, executor="@alice")

    # Should send to entity-addressed space AND named space
    assert "@alice-@charlie" in result
    assert "#general" in result

    assert (tmp_spaces / "@alice-@charlie.jsonl").exists()
    assert (tmp_spaces / "#general.jsonl").exists()
