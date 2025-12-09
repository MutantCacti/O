r"""Tests for \publish interactor."""

import pytest
from pathlib import Path
from unittest.mock import MagicMock

from interactors.publish import PublishInteractor
from grammar.parser import parse


@pytest.fixture
def publish_setup(tmp_path):
    """Set up publish interactor."""
    output_dir = tmp_path / "output"
    output_dir.mkdir()

    body = MagicMock()
    body.state = MagicMock()
    body.state.tick = 42

    publish = PublishInteractor(body=body, output_root=str(output_dir))

    return {
        "publish": publish,
        "output_dir": output_dir,
        "body": body,
    }


class TestPublishBasics:
    """Test basic publish functionality."""

    def test_publish_requires_content(self, publish_setup):
        """Publish needs filename and content."""
        publish = publish_setup["publish"]

        cmd = parse(r"\publish ---")
        result = publish.execute(cmd, executor="@alice")
        assert "ERROR" in result

    def test_publish_requires_filename_and_content(self, publish_setup):
        """Publish needs both filename and content."""
        publish = publish_setup["publish"]

        cmd = parse(r"\publish report.md ---")
        result = publish.execute(cmd, executor="@alice")
        assert "ERROR" in result
        assert "filename and content" in result.lower()

    def test_publish_writes_file(self, publish_setup):
        """Publish creates file with content."""
        publish = publish_setup["publish"]
        output_dir = publish_setup["output_dir"]

        cmd = parse(r"\publish report.md Hello World ---")
        result = publish.execute(cmd, executor="@alice")

        assert "Published" in result
        assert "report.md" in result

        # Check file
        target = output_dir / "report.md"
        assert target.exists()
        assert "Hello World" in target.read_text()

    def test_publish_includes_tick(self, publish_setup):
        """Publish result includes tick number."""
        publish = publish_setup["publish"]

        cmd = parse(r"\publish test.txt Content ---")
        result = publish.execute(cmd, executor="@alice")

        assert "tick 42" in result


class TestPublishContent:
    """Test content handling."""

    def test_publish_multiword_content(self, publish_setup):
        """Publish handles multi-word content."""
        publish = publish_setup["publish"]
        output_dir = publish_setup["output_dir"]

        cmd = parse(r"\publish test.txt This is a longer message with multiple words ---")
        publish.execute(cmd, executor="@alice")

        content = (output_dir / "test.txt").read_text()
        assert "This is a longer message with multiple words" in content

    def test_publish_appends_to_existing(self, publish_setup):
        """Publish appends to existing file."""
        publish = publish_setup["publish"]
        output_dir = publish_setup["output_dir"]

        cmd1 = parse(r"\publish log.txt First line ---")
        publish.execute(cmd1, executor="@alice")

        cmd2 = parse(r"\publish log.txt Second line ---")
        publish.execute(cmd2, executor="@alice")

        content = (output_dir / "log.txt").read_text()
        assert "First line" in content
        assert "Second line" in content

    def test_publish_adds_newline(self, publish_setup):
        """Publish adds newline if missing."""
        publish = publish_setup["publish"]
        output_dir = publish_setup["output_dir"]

        cmd = parse(r"\publish test.txt No newline ---")
        publish.execute(cmd, executor="@alice")

        content = (output_dir / "test.txt").read_text()
        assert content.endswith("\n")


class TestPublishPaths:
    """Test path handling."""

    def test_publish_creates_subdirectories(self, publish_setup):
        """Publish creates parent directories."""
        publish = publish_setup["publish"]
        output_dir = publish_setup["output_dir"]

        cmd = parse(r"\publish solutions/q1/answer.txt The answer ---")
        result = publish.execute(cmd, executor="@alice")

        assert "Published" in result
        assert (output_dir / "solutions" / "q1" / "answer.txt").exists()

    def test_publish_blocks_path_traversal(self, publish_setup):
        """Publish blocks ../ path traversal."""
        publish = publish_setup["publish"]

        cmd = parse(r"\publish ../../../etc/passwd bad content ---")
        result = publish.execute(cmd, executor="@alice")

        assert "ERROR" in result
        assert "Invalid filename" in result

    def test_publish_blocks_absolute_path(self, publish_setup):
        """Publish blocks absolute paths."""
        publish = publish_setup["publish"]

        cmd = parse(r"\publish /etc/passwd bad content ---")
        result = publish.execute(cmd, executor="@alice")

        assert "ERROR" in result


class TestPublishReadback:
    """Test reading published files."""

    def test_read_file_returns_content(self, publish_setup):
        """read_file returns published content."""
        publish = publish_setup["publish"]

        cmd = parse(r"\publish data.txt Published content ---")
        publish.execute(cmd, executor="@alice")

        content = publish.read_file("data.txt")
        assert "Published content" in content

    def test_read_file_not_found(self, publish_setup):
        """read_file returns None for missing file."""
        publish = publish_setup["publish"]

        content = publish.read_file("nonexistent.txt")
        assert content is None

    def test_read_file_blocks_traversal(self, publish_setup):
        """read_file blocks path traversal."""
        publish = publish_setup["publish"]

        content = publish.read_file("../../../etc/passwd")
        assert content is None
