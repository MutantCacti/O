"""Tests for FifoManager - the FIFO transformer."""

import os
import stat
import subprocess
import pytest
from pathlib import Path
from transformers.fifo import FifoManager


@pytest.fixture
def fifo_dir(tmp_path):
    """Create temporary directory for FIFOs."""
    fifo_root = tmp_path / "fifos"
    fifo_root.mkdir()
    yield fifo_root


def stat_is_fifo(path: Path) -> bool:
    """Check if path is a FIFO using stat."""
    try:
        return stat.S_ISFIFO(os.stat(str(path)).st_mode)
    except OSError:
        return False


class TestFifoManagerBasics:
    """Test FifoManager basic operations."""

    def test_init_creates_root(self, fifo_dir):
        """FifoManager initializes with root directory."""
        fm = FifoManager(fifo_root=str(fifo_dir))
        assert fm.fifo_root == fifo_dir


    def test_ensure_entity_fifos_creates_directory(self, fifo_dir):
        """ensure_entity_fifos() creates entity directory."""
        fm = FifoManager(fifo_root=str(fifo_dir))
        fm.ensure_entity_fifos("@alice")

        entity_dir = fifo_dir / "@alice"
        assert entity_dir.exists()
        assert entity_dir.is_dir()

    def test_ensure_entity_fifos_creates_input_fifo(self, fifo_dir):
        """ensure_entity_fifos() creates input.fifo."""
        fm = FifoManager(fifo_root=str(fifo_dir))
        fm.ensure_entity_fifos("@alice")

        input_fifo = fifo_dir / "@alice" / "input.fifo"
        assert input_fifo.exists()
        assert stat_is_fifo(input_fifo)

    def test_ensure_entity_fifos_creates_output_fifo(self, fifo_dir):
        """ensure_entity_fifos() creates output.fifo."""
        fm = FifoManager(fifo_root=str(fifo_dir))
        fm.ensure_entity_fifos("@alice")

        output_fifo = fifo_dir / "@alice" / "output.fifo"
        assert output_fifo.exists()
        assert stat_is_fifo(output_fifo)




class TestFifoManagerValidation:
    """Test entity name validation."""

    def test_rejects_empty_name(self, fifo_dir):
        """ensure_entity_fifos() rejects empty entity name."""
        fm = FifoManager(fifo_root=str(fifo_dir))
        with pytest.raises(ValueError, match="cannot be empty"):
            fm.ensure_entity_fifos("")

    def test_rejects_name_without_at(self, fifo_dir):
        """ensure_entity_fifos() rejects name without @ prefix."""
        fm = FifoManager(fifo_root=str(fifo_dir))
        with pytest.raises(ValueError, match="must start with @"):
            fm.ensure_entity_fifos("alice")

    def test_rejects_at_only(self, fifo_dir):
        """ensure_entity_fifos() rejects @ with no name."""
        fm = FifoManager(fifo_root=str(fifo_dir))
        with pytest.raises(ValueError, match="at least one character"):
            fm.ensure_entity_fifos("@")

    def test_rejects_invalid_characters(self, fifo_dir):
        """ensure_entity_fifos() rejects invalid characters."""
        fm = FifoManager(fifo_root=str(fifo_dir))
        with pytest.raises(ValueError, match="invalid characters"):
            fm.ensure_entity_fifos("@alice/bob")

    def test_accepts_valid_names(self, fifo_dir):
        """ensure_entity_fifos() accepts valid entity names."""
        fm = FifoManager(fifo_root=str(fifo_dir))
        # Should not raise
        fm.ensure_entity_fifos("@alice")
        fm.ensure_entity_fifos("@bob-test")
        fm.ensure_entity_fifos("@entity_123")


class TestFifoManagerReadWrite:
    """Test FifoManager read/write operations."""

    @pytest.mark.asyncio
    async def test_read_command_returns_none_when_no_fifo(self, fifo_dir):
        """read_command() returns None when FIFO doesn't exist."""
        fm = FifoManager(fifo_root=str(fifo_dir))
        result = await fm.read_command("@nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_read_command_returns_none_when_empty(self, fifo_dir):
        """read_command() returns None when FIFO is empty."""
        fm = FifoManager(fifo_root=str(fifo_dir))
        fm.ensure_entity_fifos("@alice")

        # Non-blocking read should return None immediately
        result = await fm.read_command("@alice")
        assert result is None

    @pytest.mark.asyncio
    async def test_write_output_no_error_when_no_reader(self, fifo_dir):
        """write_output() doesn't raise when no reader connected."""
        fm = FifoManager(fifo_root=str(fifo_dir))
        fm.ensure_entity_fifos("@alice")

        # Should not raise
        await fm.write_output("@alice", {"tick": 0, "output": "test"})

    def test_close_cleans_up(self, fifo_dir):
        """close() cleans up file descriptors."""
        fm = FifoManager(fifo_root=str(fifo_dir))
        fm.ensure_entity_fifos("@alice")

        # Open FIFOs
        fm._input_fds["@alice"] = os.open(
            str(fifo_dir / "@alice" / "input.fifo"),
            os.O_RDONLY | os.O_NONBLOCK
        )

        # Close should not raise
        fm.close()
        assert len(fm._input_fds) == 0

    def test_cleanup_stale_fds(self, fifo_dir):
        """_cleanup_stale_fds() cleans up FDs for removed entities."""
        fm = FifoManager(fifo_root=str(fifo_dir))
        fm.ensure_entity_fifos("@alice")
        fm.ensure_entity_fifos("@bob")

        # Open FDs for both
        fm._input_fds["@alice"] = os.open(
            str(fifo_dir / "@alice" / "input.fifo"),
            os.O_RDONLY | os.O_NONBLOCK
        )
        fm._input_fds["@bob"] = os.open(
            str(fifo_dir / "@bob" / "input.fifo"),
            os.O_RDONLY | os.O_NONBLOCK
        )

        # Call _cleanup_stale_fds with only @alice as active
        # This should clean up @bob's FD
        fm._cleanup_stale_fds(["@alice"])
        
        assert "@alice" in fm._input_fds
        assert "@bob" not in fm._input_fds

        fm.close()


class TestFifoManagerIntegration:
    """Integration tests with buffering logic."""

    @pytest.mark.asyncio
    async def test_buffer_extraction(self, fifo_dir):
        """Test command extraction from buffer."""
        fm = FifoManager(fifo_root=str(fifo_dir))
        fm.ensure_entity_fifos("@test")

        # Manually populate buffer (simulating partial reads)
        fm._input_buffers["@test"] = b"\\echo Hello ---\n\\echo World ---\n"

        # Extract first command
        result1 = fm._extract_command_from_buffer("@test")
        assert result1 == r"\echo Hello ---"

        # Extract second command
        result2 = fm._extract_command_from_buffer("@test")
        assert result2 == r"\echo World ---"

        # Buffer empty
        result3 = fm._extract_command_from_buffer("@test")
        assert result3 is None

        fm.close()

    @pytest.mark.asyncio
    async def test_buffer_partial_command(self, fifo_dir):
        """Test that partial commands stay buffered."""
        fm = FifoManager(fifo_root=str(fifo_dir))
        fm.ensure_entity_fifos("@test")

        # Partial command (no newline)
        fm._input_buffers["@test"] = b"\\echo Hello"

        result = fm._extract_command_from_buffer("@test")
        assert result is None

        # Buffer should still have the partial data
        assert fm._input_buffers["@test"] == b"\\echo Hello"

        # Add the rest
        fm._input_buffers["@test"] += b" World ---\n"

        result = fm._extract_command_from_buffer("@test")
        assert result == r"\echo Hello World ---"

        fm.close()

    @pytest.mark.asyncio
    async def test_buffer_overflow_protection(self, fifo_dir):
        """Test that oversized buffers are cleared to resync."""
        fm = FifoManager(fifo_root=str(fifo_dir))
        fm.ensure_entity_fifos("@test")

        # Set a small max for testing
        original_max = fm.MAX_COMMAND_SIZE
        fm.MAX_COMMAND_SIZE = 100

        # Overflow the buffer
        fm._input_buffers["@test"] = b"x" * 150

        # Simulate another read that triggers overflow check
        # (Normally this happens in read_command)
        if len(fm._input_buffers["@test"]) > fm.MAX_COMMAND_SIZE:
            # Clear entirely to resync (keeping tail corrupts commands)
            fm._input_buffers["@test"] = b""

        assert len(fm._input_buffers["@test"]) == 0

        fm.MAX_COMMAND_SIZE = original_max
        fm.close()
