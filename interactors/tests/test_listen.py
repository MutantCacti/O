r"""Tests for \listen interactor."""

import pytest
from pathlib import Path
from interactors.listen import ListenInteractor
from grammar.parser import parse


@pytest.fixture
def listen_dir(tmp_path):
    """Create temporary listen directory."""
    listen_path = tmp_path / "listen"
    listen_path.mkdir()
    return listen_path


@pytest.fixture
def listen(listen_dir):
    """Listen interactor with temp dir."""
    return ListenInteractor(memory_root=str(listen_dir))


class TestListenBasics:
    """Test basic listen functionality."""

    def test_listen_requires_executor(self, listen):
        """Listen needs to know who is subscribing."""
        cmd = parse(r"\listen @bob ---")
        result = listen.execute(cmd, executor=None)
        assert "ERROR" in result
        assert "requires executor" in result

    def test_listen_requires_targets(self, listen):
        """Listen needs at least one target."""
        cmd = parse(r"\listen ---")
        result = listen.execute(cmd, executor="@alice")
        assert "ERROR" in result
        assert "No targets" in result

    def test_listen_subscribes_to_entity(self, listen):
        """Listen subscribes to entity space."""
        cmd = parse(r"\listen @bob ---")
        result = listen.execute(cmd, executor="@alice")

        assert "Listening to" in result
        assert "@bob" in result
        assert "@bob" in listen.get_subscriptions("@alice")

    def test_listen_subscribes_to_space(self, listen):
        """Listen subscribes to named space."""
        cmd = parse(r"\listen #general ---")
        result = listen.execute(cmd, executor="@alice")

        assert "Listening to" in result
        assert "#general" in result
        assert "#general" in listen.get_subscriptions("@alice")

    def test_listen_multiple_targets(self, listen):
        """Listen can subscribe to multiple targets at once."""
        cmd = parse(r"\listen @bob @charlie #general ---")
        result = listen.execute(cmd, executor="@alice")

        subs = listen.get_subscriptions("@alice")
        assert "@bob" in subs
        assert "@charlie" in subs
        assert "#general" in subs

    def test_listen_merges_subscriptions(self, listen):
        """Multiple listen calls merge subscriptions."""
        cmd1 = parse(r"\listen @bob ---")
        listen.execute(cmd1, executor="@alice")

        cmd2 = parse(r"\listen @charlie ---")
        listen.execute(cmd2, executor="@alice")

        subs = listen.get_subscriptions("@alice")
        assert "@bob" in subs
        assert "@charlie" in subs

    def test_listen_no_duplicates(self, listen):
        """Listening to same target twice doesn't duplicate."""
        cmd = parse(r"\listen @bob ---")
        listen.execute(cmd, executor="@alice")
        listen.execute(cmd, executor="@alice")

        subs = listen.get_subscriptions("@alice")
        assert subs.count("@bob") == 1


class TestGetSubscriptions:
    """Test get_subscriptions helper."""

    def test_get_subscriptions_empty(self, listen):
        """No subscriptions returns empty list."""
        assert listen.get_subscriptions("@alice") == []

    def test_get_subscriptions_returns_list(self, listen):
        """get_subscriptions returns list of spaces."""
        cmd = parse(r"\listen @bob #general ---")
        listen.execute(cmd, executor="@alice")

        subs = listen.get_subscriptions("@alice")
        assert isinstance(subs, list)
        assert len(subs) == 2
