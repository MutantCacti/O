r"""Tests for \incoming interactor."""

import pytest
import json
from pathlib import Path
from unittest.mock import MagicMock
from interactors.incoming import IncomingInteractor
from grammar.parser import parse


@pytest.fixture
def incoming_dirs(tmp_path):
    """Create temporary directories for incoming."""
    spaces = tmp_path / "spaces"
    state = tmp_path / "incoming"
    spaces.mkdir()
    state.mkdir()
    return spaces, state


@pytest.fixture
def mock_body():
    """Mock body with entity_spaces."""
    body = MagicMock()
    body.entity_spaces = {}
    return body


@pytest.fixture
def incoming(incoming_dirs, mock_body):
    """Incoming interactor with temp dirs and mock body."""
    spaces, state = incoming_dirs
    return IncomingInteractor(body=mock_body, spaces_root=str(spaces), state_root=str(state))


class TestIncomingBasics:
    """Test basic incoming functionality."""

    def test_incoming_requires_executor(self, incoming):
        """Incoming needs to know who is checking."""
        cmd = parse(r"\incoming ---")
        result = incoming.execute(cmd, executor=None)
        assert "ERROR" in result
        assert "requires executor" in result

    def test_incoming_returns_false_when_no_spaces(self, incoming):
        """No space files = no messages."""
        cmd = parse(r"\incoming ---")
        result = incoming.execute(cmd, executor="@alice")
        assert result == "false"

    def test_incoming_returns_false_when_empty_space(self, incoming_dirs, incoming, mock_body):
        """Empty space file = no messages."""
        spaces, _ = incoming_dirs

        # Register space in body.entity_spaces
        mock_body.entity_spaces["@alice"] = {"@alice-@bob"}

        # Create empty space file
        (spaces / "@alice-@bob.jsonl").touch()

        cmd = parse(r"\incoming ---")
        result = incoming.execute(cmd, executor="@alice")
        assert result == "false"


class TestIncomingWithMessages:
    """Test incoming with actual messages."""

    def test_incoming_returns_true_on_first_message(self, incoming_dirs, incoming, mock_body):
        """First message in space triggers true."""
        spaces, _ = incoming_dirs

        # Register space in body.entity_spaces
        mock_body.entity_spaces["@alice"] = {"@alice-@bob"}

        # Create space with one message
        space_file = spaces / "@alice-@bob.jsonl"
        with open(space_file, "w") as f:
            f.write(json.dumps({"sender": "@bob", "content": "Hello"}) + "\n")

        cmd = parse(r"\incoming ---")
        result = incoming.execute(cmd, executor="@alice")
        assert result == "true"

    def test_incoming_returns_false_on_same_count(self, incoming_dirs, incoming, mock_body):
        """No new messages = false."""
        spaces, _ = incoming_dirs

        # Register space in body.entity_spaces
        mock_body.entity_spaces["@alice"] = {"@alice-@bob"}

        # Create space with one message
        space_file = spaces / "@alice-@bob.jsonl"
        with open(space_file, "w") as f:
            f.write(json.dumps({"sender": "@bob", "content": "Hello"}) + "\n")

        cmd = parse(r"\incoming ---")

        # First check - sees new message
        result = incoming.execute(cmd, executor="@alice")
        assert result == "true"

        # Second check - no new messages
        result = incoming.execute(cmd, executor="@alice")
        assert result == "false"

    def test_incoming_returns_true_on_new_message(self, incoming_dirs, incoming, mock_body):
        """New message after check triggers true."""
        spaces, _ = incoming_dirs

        # Register space in body.entity_spaces
        mock_body.entity_spaces["@alice"] = {"@alice-@bob"}

        space_file = spaces / "@alice-@bob.jsonl"
        with open(space_file, "w") as f:
            f.write(json.dumps({"sender": "@bob", "content": "First"}) + "\n")

        cmd = parse(r"\incoming ---")

        # First check
        incoming.execute(cmd, executor="@alice")

        # Add new message
        with open(space_file, "a") as f:
            f.write(json.dumps({"sender": "@bob", "content": "Second"}) + "\n")

        # Second check - sees new message
        result = incoming.execute(cmd, executor="@alice")
        assert result == "true"


class TestIncomingMultipleSpaces:
    """Test incoming with multiple spaces."""

    def test_incoming_checks_multiple_spaces(self, incoming_dirs, incoming, mock_body):
        """Incoming checks all spaces entity is part of."""
        spaces, _ = incoming_dirs

        # Register spaces in body.entity_spaces
        mock_body.entity_spaces["@alice"] = {"@alice-@bob", "@alice-@charlie"}

        # Create two space files for alice
        with open(spaces / "@alice-@bob.jsonl", "w") as f:
            f.write(json.dumps({"sender": "@bob", "content": "Hi"}) + "\n")

        with open(spaces / "@alice-@charlie.jsonl", "w") as f:
            f.write(json.dumps({"sender": "@charlie", "content": "Hey"}) + "\n")

        cmd = parse(r"\incoming ---")
        result = incoming.execute(cmd, executor="@alice")
        assert result == "true"

    def test_incoming_ignores_other_spaces(self, incoming_dirs, incoming, mock_body):
        """Incoming ignores spaces entity isn't in."""
        spaces, _ = incoming_dirs

        # Alice not in any spaces (empty entity_spaces)
        mock_body.entity_spaces["@alice"] = set()

        # Create space that doesn't include alice
        with open(spaces / "@bob-@charlie.jsonl", "w") as f:
            f.write(json.dumps({"sender": "@bob", "content": "Private"}) + "\n")

        cmd = parse(r"\incoming ---")
        result = incoming.execute(cmd, executor="@alice")
        assert result == "false"
