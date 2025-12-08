"""Tests for app.py - Application lifecycle and integration."""

import pytest
import asyncio
from pathlib import Path
import tempfile
import shutil

from app import App
from transformers.human import HumanTransformer


class TestAppInitialization:
    """Test App class initialization and configuration."""

    def test_app_defaults(self):
        """App uses default configuration."""
        app = App()
        assert app.tick_interval == 1.0
        assert app.state_dir == Path("state")
        assert app.memory_dir == Path("memory")
        assert app.body is None

    def test_app_custom_config(self):
        """App accepts custom configuration."""
        app = App(
            tick_interval=0.5,
            state_dir=Path("/tmp/state"),
            memory_dir=Path("/tmp/memory")
        )
        assert app.tick_interval == 0.5
        assert app.state_dir == Path("/tmp/state")
        assert app.memory_dir == Path("/tmp/memory")


class TestAppValidation:
    """Test configuration validation."""

    @pytest.mark.asyncio
    async def test_negative_tick_interval(self):
        """Negative tick_interval raises ValueError."""
        app = App(tick_interval=-1.0)
        with pytest.raises(ValueError, match="tick_interval must be positive"):
            await app.start(max_ticks=1)

    @pytest.mark.asyncio
    async def test_zero_tick_interval(self):
        """Zero tick_interval raises ValueError."""
        app = App(tick_interval=0.0)
        with pytest.raises(ValueError, match="tick_interval must be positive"):
            await app.start(max_ticks=1)


class TestAppLifecycle:
    """Test App startup, execution, and shutdown."""

    @pytest.mark.asyncio
    async def test_app_starts_and_stops(self, tmp_path):
        """App can start and stop cleanly."""
        app = App(
            tick_interval=0.01,
            state_dir=tmp_path / "state",
            memory_dir=tmp_path / "memory"
        )

        # Run for 2 ticks
        await app.start(max_ticks=2)

        # Verify body was created
        assert app.body is not None

        # Verify state advanced
        assert app.body.state.tick == 2

    @pytest.mark.asyncio
    async def test_app_creates_directories(self, tmp_path):
        """App creates required directories on start."""
        state_dir = tmp_path / "state"
        memory_dir = tmp_path / "memory"

        app = App(
            tick_interval=0.01,
            state_dir=state_dir,
            memory_dir=memory_dir
        )

        await app.start(max_ticks=1)

        # Verify directories exist
        assert state_dir.exists()
        assert memory_dir.exists()
        assert (memory_dir / "stdout").exists()
        assert (memory_dir / "spaces").exists()

    @pytest.mark.asyncio
    async def test_app_initializes_components(self, tmp_path):
        """App initializes Mind, Body, State, and Transformers."""
        app = App(
            tick_interval=0.01,
            state_dir=tmp_path / "state",
            memory_dir=tmp_path / "memory"
        )

        await app.start(max_ticks=1)

        # Verify components exist
        assert app.body is not None
        assert app.body.mind is not None
        assert app.body.state is not None
        assert app.body.transformer is not None

        # Verify interactors registered
        assert "echo" in app.body.mind.interactors
        assert "stdout" in app.body.mind.interactors
        assert "say" in app.body.mind.interactors
        assert "name" in app.body.mind.interactors
        assert "wake" in app.body.mind.interactors

    @pytest.mark.asyncio
    async def test_app_wires_body_references(self, tmp_path):
        """App wires body references to interactors that need them."""
        app = App(
            tick_interval=0.01,
            state_dir=tmp_path / "state",
            memory_dir=tmp_path / "memory"
        )

        await app.start(max_ticks=1)

        # Check interactors that need body reference have it
        stdout = app.body.mind.interactors["stdout"]
        assert hasattr(stdout, 'body')
        assert stdout.body is app.body

        say = app.body.mind.interactors["say"]
        assert hasattr(say, 'body')
        assert say.body is app.body

        wake = app.body.mind.interactors["wake"]
        assert hasattr(wake, 'body')
        assert wake.body is app.body


class TestAppExecution:
    """Test App executes commands through full pipeline."""

    @pytest.mark.asyncio
    async def test_app_runs_multiple_ticks(self, tmp_path):
        """App runs through multiple ticks correctly."""
        app = App(
            tick_interval=0.01,
            state_dir=tmp_path / "state",
            memory_dir=tmp_path / "memory"
        )

        await app.start(max_ticks=5)

        # Verify ticks advanced
        assert app.body.state.tick == 5

    @pytest.mark.asyncio
    async def test_app_has_transformer(self, tmp_path):
        """App initializes with transformer service."""
        app = App(
            tick_interval=0.01,
            state_dir=tmp_path / "state",
            memory_dir=tmp_path / "memory"
        )

        await app.start(max_ticks=1)

        # Verify transformer is set
        assert app.body.transformer is not None
        assert isinstance(app.body.transformer, HumanTransformer)


class TestAppErrorHandling:
    """Test App handles errors gracefully."""

    @pytest.mark.asyncio
    async def test_app_handles_directory_creation_error(self, tmp_path):
        """App raises clear error if directory creation fails."""
        # Create a file where directory should be
        bad_path = tmp_path / "blocked"
        bad_path.write_text("blocking file")

        app = App(
            tick_interval=0.01,
            state_dir=bad_path,  # This will fail
            memory_dir=tmp_path / "memory"
        )

        with pytest.raises(OSError):
            await app.start(max_ticks=1)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
