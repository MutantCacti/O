r"""Tests for \read interactor."""

import pytest
import json
from pathlib import Path
from unittest.mock import MagicMock

from interactors.read import ReadInteractor
from grammar.parser import parse


@pytest.fixture
def read_setup(tmp_path):
    """Set up read interactor with mock body."""
    spaces_dir = tmp_path / "spaces"
    state_dir = tmp_path / "read_state"
    spaces_dir.mkdir()
    state_dir.mkdir()

    body = MagicMock()
    body.entity_spaces = {}

    read = ReadInteractor(
        body=body,
        spaces_root=str(spaces_dir),
        state_root=str(state_dir)
    )

    return {
        "read": read,
        "body": body,
        "spaces_dir": spaces_dir,
        "state_dir": state_dir,
    }


def write_message(spaces_dir: Path, space_id: str, sender: str, content: str):
    """Helper to write a message to a space file."""
    space_file = spaces_dir / f"{space_id}.jsonl"
    with open(space_file, "a") as f:
        f.write(json.dumps({"sender": sender, "content": content}) + "\n")


class TestReadBasics:
    """Test basic read functionality."""

    def test_read_requires_executor(self, read_setup):
        """Read needs executor context."""
        read = read_setup["read"]
        cmd = parse(r"\read ---")

        result = read.execute(cmd, executor=None)
        assert "ERROR" in result
        assert "executor" in result.lower()

    def test_read_no_spaces_returns_message(self, read_setup):
        """Read with no subscribed spaces returns appropriate message."""
        read = read_setup["read"]
        cmd = parse(r"\read ---")

        result = read.execute(cmd, executor="@alice")
        assert "No subscribed spaces" in result

    def test_read_no_messages(self, read_setup):
        """Read with spaces but no messages returns no new messages."""
        read = read_setup["read"]
        body = read_setup["body"]

        # Alice is in a space but no messages
        body.entity_spaces["@alice"] = {"@alice-@bob"}

        cmd = parse(r"\read ---")
        result = read.execute(cmd, executor="@alice")

        assert "No new messages" in result


class TestReadMessages:
    """Test reading actual messages."""

    def test_read_single_message(self, read_setup):
        """Read returns a single message."""
        read = read_setup["read"]
        body = read_setup["body"]
        spaces_dir = read_setup["spaces_dir"]

        # Set up space membership
        body.entity_spaces["@alice"] = {"@alice-@bob"}

        # Bob sends a message
        write_message(spaces_dir, "@alice-@bob", "@bob", "Hello Alice!")

        cmd = parse(r"\read ---")
        result = read.execute(cmd, executor="@alice")

        assert "@bob" in result
        assert "Hello Alice" in result
        assert "@alice-@bob" in result

    def test_read_multiple_messages(self, read_setup):
        """Read returns multiple messages."""
        read = read_setup["read"]
        body = read_setup["body"]
        spaces_dir = read_setup["spaces_dir"]

        body.entity_spaces["@alice"] = {"@alice-@bob"}

        write_message(spaces_dir, "@alice-@bob", "@bob", "First message")
        write_message(spaces_dir, "@alice-@bob", "@bob", "Second message")
        write_message(spaces_dir, "@alice-@bob", "@alice", "My reply")

        cmd = parse(r"\read ---")
        result = read.execute(cmd, executor="@alice")

        assert "First message" in result
        assert "Second message" in result
        assert "My reply" in result

    def test_read_marks_as_read(self, read_setup):
        """Messages are marked as read after reading."""
        read = read_setup["read"]
        body = read_setup["body"]
        spaces_dir = read_setup["spaces_dir"]

        body.entity_spaces["@alice"] = {"@alice-@bob"}

        write_message(spaces_dir, "@alice-@bob", "@bob", "Hello!")

        cmd = parse(r"\read ---")

        # First read - gets message
        result = read.execute(cmd, executor="@alice")
        assert "Hello" in result

        # Second read - no new messages
        result = read.execute(cmd, executor="@alice")
        assert "No new messages" in result

    def test_read_only_unread(self, read_setup):
        """Read only returns messages since last read."""
        read = read_setup["read"]
        body = read_setup["body"]
        spaces_dir = read_setup["spaces_dir"]

        body.entity_spaces["@alice"] = {"@alice-@bob"}

        # Write first message and read it
        write_message(spaces_dir, "@alice-@bob", "@bob", "First")
        cmd = parse(r"\read ---")
        read.execute(cmd, executor="@alice")

        # Write second message
        write_message(spaces_dir, "@alice-@bob", "@bob", "Second")

        # Read again - should only get second message
        result = read.execute(cmd, executor="@alice")
        assert "Second" in result
        assert "First" not in result


class TestReadFiltering:
    """Test filtering by target."""

    def test_read_specific_entity(self, read_setup):
        """Read from specific entity."""
        read = read_setup["read"]
        body = read_setup["body"]
        spaces_dir = read_setup["spaces_dir"]

        body.entity_spaces["@alice"] = {"@alice-@bob", "@alice-@charlie"}

        write_message(spaces_dir, "@alice-@bob", "@bob", "From Bob")
        write_message(spaces_dir, "@alice-@charlie", "@charlie", "From Charlie")

        # Read only from Bob
        cmd = parse(r"\read @bob ---")
        result = read.execute(cmd, executor="@alice")

        assert "From Bob" in result
        assert "From Charlie" not in result

    def test_read_specific_space(self, read_setup):
        """Read from specific named space."""
        read = read_setup["read"]
        body = read_setup["body"]
        spaces_dir = read_setup["spaces_dir"]

        body.entity_spaces["@alice"] = {"#general", "#dev"}

        write_message(spaces_dir, "#general", "@bob", "General message")
        write_message(spaces_dir, "#dev", "@charlie", "Dev message")

        # Read only from #general
        cmd = parse(r"\read #general ---")
        result = read.execute(cmd, executor="@alice")

        assert "General message" in result
        assert "Dev message" not in result


class TestReadMultipleSpaces:
    """Test reading from multiple spaces."""

    def test_read_all_spaces(self, read_setup):
        """Read from all subscribed spaces."""
        read = read_setup["read"]
        body = read_setup["body"]
        spaces_dir = read_setup["spaces_dir"]

        body.entity_spaces["@alice"] = {"@alice-@bob", "#general"}

        write_message(spaces_dir, "@alice-@bob", "@bob", "DM from Bob")
        write_message(spaces_dir, "#general", "@charlie", "Public message")

        cmd = parse(r"\read ---")
        result = read.execute(cmd, executor="@alice")

        assert "DM from Bob" in result
        assert "Public message" in result

    def test_read_multiple_targets(self, read_setup):
        """Read from multiple specified targets."""
        read = read_setup["read"]
        body = read_setup["body"]
        spaces_dir = read_setup["spaces_dir"]

        body.entity_spaces["@alice"] = {"@alice-@bob", "@alice-@charlie", "#general"}

        write_message(spaces_dir, "@alice-@bob", "@bob", "From Bob")
        write_message(spaces_dir, "@alice-@charlie", "@charlie", "From Charlie")
        write_message(spaces_dir, "#general", "@dave", "From Dave")

        # Read from Bob and #general, not Charlie
        cmd = parse(r"\read @bob #general ---")
        result = read.execute(cmd, executor="@alice")

        assert "From Bob" in result
        assert "From Dave" in result
        assert "From Charlie" not in result

    def test_read_multiple_entities_grouped(self, read_setup):
        """Read from multiple entities using @(alice, bob) syntax."""
        read = read_setup["read"]
        body = read_setup["body"]
        spaces_dir = read_setup["spaces_dir"]

        body.entity_spaces["@alice"] = {"@alice-@bob", "@alice-@charlie", "@alice-@dave"}

        write_message(spaces_dir, "@alice-@bob", "@bob", "From Bob")
        write_message(spaces_dir, "@alice-@charlie", "@charlie", "From Charlie")
        write_message(spaces_dir, "@alice-@dave", "@dave", "From Dave")

        # Read from Bob and Charlie using grouped syntax
        cmd = parse(r"\read @(bob, charlie) ---")
        result = read.execute(cmd, executor="@alice")

        assert "From Bob" in result
        assert "From Charlie" in result
        assert "From Dave" not in result
