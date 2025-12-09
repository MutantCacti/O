r"""Tests for wake interactor."""

import pytest
import json
from pathlib import Path
from interactors.wake import WakeInteractor
from interactors.up import UpInteractor
from interactors.listen import ListenInteractor
from grammar.parser import parse
from mind import Mind


@pytest.fixture
def wake_dir(tmp_path):
    """Create temporary wake directory."""
    wake_path = tmp_path / "wake"
    wake_path.mkdir()
    return wake_path


@pytest.fixture
def wake_with_mind(wake_dir):
    """Wake interactor with mind for condition evaluation."""
    up = UpInteractor()
    mind = Mind({"up": up})
    wake = WakeInteractor(mind=mind, memory_root=str(wake_dir))
    return wake


class TestWakeRegistration:
    """Test wake condition registration."""

    def test_wake_requires_executor(self, wake_dir):
        """Wake needs to know who is sleeping."""
        wake = WakeInteractor(memory_root=str(wake_dir))
        cmd = parse(r"\wake ?($(\up---)) Check messages ---")

        result = wake.execute(cmd, executor=None)
        assert "ERROR" in result
        assert "requires executor" in result

    def test_wake_requires_condition(self, wake_dir):
        """Wake needs a ?() condition."""
        wake = WakeInteractor(memory_root=str(wake_dir))
        cmd = parse(r"\wake No condition here ---")

        result = wake.execute(cmd, executor="@alice")
        assert "ERROR" in result
        assert "No condition" in result

    def test_wake_registers_condition(self, wake_dir):
        """Wake saves condition to file."""
        wake = WakeInteractor(memory_root=str(wake_dir))
        cmd = parse(r"\wake ?($(\up---)) Check messages ---")

        result = wake.execute(cmd, executor="@alice")

        assert "Wake registered" in result
        assert wake.has_wake_record("@alice")

    def test_wake_stores_self_prompt(self, wake_dir):
        """Wake saves self-prompt with condition."""
        wake = WakeInteractor(memory_root=str(wake_dir))
        cmd = parse(r"\wake ?($(\up---)) Remember to check inbox ---")

        wake.execute(cmd, executor="@alice")

        record = wake._load_record("@alice")
        assert record is not None
        assert record["self_prompt"] == "Remember to check inbox"

    def test_wake_without_prompt(self, wake_dir):
        """Wake can register without self-prompt."""
        wake = WakeInteractor(memory_root=str(wake_dir))
        cmd = parse(r"\wake ?($(\up---)) ---")

        result = wake.execute(cmd, executor="@alice")

        assert "Wake registered" in result
        record = wake._load_record("@alice")
        assert record["self_prompt"] is None

    def test_wake_overwrites_previous(self, wake_dir):
        """Calling wake twice updates the condition."""
        wake = WakeInteractor(memory_root=str(wake_dir))

        cmd1 = parse(r"\wake ?($(\up---)) First prompt ---")
        wake.execute(cmd1, executor="@alice")

        cmd2 = parse(r"\wake ?($(\up---)) Second prompt ---")
        wake.execute(cmd2, executor="@alice")

        record = wake._load_record("@alice")
        assert record["self_prompt"] == "Second prompt"

    def test_wake_multiple_entities(self, wake_dir):
        """Multiple entities can register wake conditions."""
        wake = WakeInteractor(memory_root=str(wake_dir))

        cmd1 = parse(r"\wake ?($(\up---)) Alice prompt ---")
        wake.execute(cmd1, executor="@alice")

        cmd2 = parse(r"\wake ?($(\up---)) Bob prompt ---")
        wake.execute(cmd2, executor="@bob")

        assert wake.has_wake_record("@alice")
        assert wake.has_wake_record("@bob")


class TestWakeEvaluation:
    """Test wake condition evaluation."""

    @pytest.mark.asyncio
    async def test_should_wake_returns_false_without_record(self, wake_with_mind):
        """No record = no wake."""
        wake = wake_with_mind
        should, prompt = await wake.should_wake("@alice")
        assert should is False
        assert prompt is None

    @pytest.mark.asyncio
    async def test_should_wake_evaluates_condition(self, wake_with_mind):
        """should_wake evaluates ?() condition via eval."""
        wake = wake_with_mind

        # Register with \up (always true)
        cmd = parse(r"\wake ?($(\up---)) My prompt ---")
        wake.execute(cmd, executor="@alice")

        should, prompt = await wake.should_wake("@alice")
        assert should is True
        assert prompt == "My prompt"

    @pytest.mark.asyncio
    async def test_should_wake_clears_record_on_wake(self, wake_with_mind):
        """Wake record is consumed after waking."""
        wake = wake_with_mind

        cmd = parse(r"\wake ?($(\up---)) My prompt ---")
        wake.execute(cmd, executor="@alice")

        # First check - wakes and clears
        should, _ = await wake.should_wake("@alice")
        assert should is True

        # Second check - no more record
        should, prompt = await wake.should_wake("@alice")
        assert should is False
        assert prompt is None

    @pytest.mark.asyncio
    async def test_should_wake_without_mind(self, wake_dir):
        """Without mind, can't evaluate conditions."""
        wake = WakeInteractor(memory_root=str(wake_dir))  # No mind

        cmd = parse(r"\wake ?($(\up---)) My prompt ---")
        wake.execute(cmd, executor="@alice")

        should, prompt = await wake.should_wake("@alice")
        assert should is False  # Can't evaluate without mind


class TestWakeHelpers:
    """Test wake helper methods."""

    def test_has_wake_record_true(self, wake_dir):
        """has_wake_record returns True when record exists."""
        wake = WakeInteractor(memory_root=str(wake_dir))

        cmd = parse(r"\wake ?($(\up---)) Prompt ---")
        wake.execute(cmd, executor="@alice")

        assert wake.has_wake_record("@alice") is True

    def test_has_wake_record_false(self, wake_dir):
        """has_wake_record returns False when no record."""
        wake = WakeInteractor(memory_root=str(wake_dir))
        assert wake.has_wake_record("@alice") is False


class TestWakeWithListen:
    """Test wake with listen integration for message bundling."""

    @pytest.fixture
    def full_setup(self, tmp_path):
        """Set up wake with listen and spaces."""
        wake_dir = tmp_path / "wake"
        listen_dir = tmp_path / "listen"
        spaces_dir = tmp_path / "spaces"
        wake_dir.mkdir()
        listen_dir.mkdir()
        spaces_dir.mkdir()

        up = UpInteractor()
        mind = Mind({"up": up})
        listen = ListenInteractor(memory_root=str(listen_dir))
        wake = WakeInteractor(
            mind=mind,
            memory_root=str(wake_dir),
            listen=listen,
            spaces_root=str(spaces_dir)
        )

        return wake, listen, spaces_dir

    @pytest.mark.asyncio
    async def test_wake_includes_messages_from_listened_spaces(self, full_setup):
        """Wake bundles messages from listened spaces into prompt."""
        wake, listen, spaces_dir = full_setup

        # Alice listens to Bob
        listen_cmd = parse(r"\listen @bob ---")
        listen.execute(listen_cmd, executor="@alice")

        # Bob sends a message (space file: @alice-@bob.jsonl)
        space_file = spaces_dir / "@alice-@bob.jsonl"
        with open(space_file, "w") as f:
            f.write(json.dumps({"sender": "@bob", "content": "Hello Alice!"}) + "\n")

        # Alice registers wake
        wake_cmd = parse(r"\wake ?($(\up---)) Check messages ---")
        wake.execute(wake_cmd, executor="@alice")

        # Check wake - should include message
        should, prompt = await wake.should_wake("@alice")

        assert should is True
        assert "Check messages" in prompt
        assert "--- Messages ---" in prompt
        assert "@bob: Hello Alice!" in prompt

    @pytest.mark.asyncio
    async def test_wake_without_listen_no_messages(self, wake_dir):
        """Wake without listen interactor returns just self_prompt."""
        up = UpInteractor()
        mind = Mind({"up": up})
        wake = WakeInteractor(mind=mind, memory_root=str(wake_dir))  # No listen

        wake_cmd = parse(r"\wake ?($(\up---)) My prompt ---")
        wake.execute(wake_cmd, executor="@alice")

        should, prompt = await wake.should_wake("@alice")

        assert should is True
        assert prompt == "My prompt"
        assert "Messages" not in prompt

    @pytest.mark.asyncio
    async def test_wake_with_listen_but_no_messages(self, full_setup):
        """Wake with listen but no messages returns just self_prompt."""
        wake, listen, spaces_dir = full_setup

        # Alice listens to Bob but no messages yet
        listen_cmd = parse(r"\listen @bob ---")
        listen.execute(listen_cmd, executor="@alice")

        wake_cmd = parse(r"\wake ?($(\up---)) Waiting for Bob ---")
        wake.execute(wake_cmd, executor="@alice")

        should, prompt = await wake.should_wake("@alice")

        assert should is True
        assert prompt == "Waiting for Bob"

    @pytest.mark.asyncio
    async def test_wake_multiple_messages(self, full_setup):
        """Wake bundles multiple messages."""
        wake, listen, spaces_dir = full_setup

        listen_cmd = parse(r"\listen @bob ---")
        listen.execute(listen_cmd, executor="@alice")

        space_file = spaces_dir / "@alice-@bob.jsonl"
        with open(space_file, "w") as f:
            f.write(json.dumps({"sender": "@bob", "content": "First message"}) + "\n")
            f.write(json.dumps({"sender": "@alice", "content": "Reply"}) + "\n")
            f.write(json.dumps({"sender": "@bob", "content": "Second message"}) + "\n")

        wake_cmd = parse(r"\wake ?($(\up---)) Check thread ---")
        wake.execute(wake_cmd, executor="@alice")

        should, prompt = await wake.should_wake("@alice")

        assert should is True
        assert "@bob: First message" in prompt
        assert "@alice: Reply" in prompt
        assert "@bob: Second message" in prompt
