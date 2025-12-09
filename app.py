"""
app.py - O Application Entry Point

Manages the async event loop, signal handling, and lifecycle of O.

Usage:
    python app.py                    # Run with defaults
    python app.py --tick-interval 2  # Custom tick interval
"""

import asyncio
import signal
import sys
from pathlib import Path
from typing import List, Optional

from body import Body
from mind import Mind
from state.state import SystemState
from interactors.echo import EchoInteractor
from interactors.stdout import StdoutInteractor
from interactors.say import SayInteractor
from interactors.name import NameInteractor
from interactors.wake import WakeInteractor
from interactors.spawn import SpawnInteractor
from interactors.up import UpInteractor
from interactors.incoming import IncomingInteractor
from interactors.listen import ListenInteractor
from transformers.fifo import FifoManager


class App:
    """
    O Application lifecycle manager.

    Handles:
    - Component initialization
    - Async event loop
    - Signal handling for graceful shutdown
    - Transformer registration
    """

    def __init__(
        self,
        tick_interval: float = 1.0,
        state_dir: Path = None,
        memory_dir: Path = None
    ):
        """
        Initialize O application.

        Args:
            tick_interval: Seconds between ticks
            state_dir: Directory for state/logs (default: ./state)
            memory_dir: Directory for memory storage (default: ./memory)
        """
        self.tick_interval = tick_interval
        self.state_dir = state_dir or Path("state")
        self.memory_dir = memory_dir or Path("memory")

        self.body: Optional[Body] = None
        self._shutdown_event: Optional[asyncio.Event] = None

    def _build_interactors(self) -> dict:
        """Build interactor registry with body reference."""
        # Create interactors (body reference added after Body creation)
        # Create listen first since wake depends on it
        listen = ListenInteractor(memory_root=str(self.memory_dir / "listen"))

        return {
            "echo": EchoInteractor(),
            "stdout": StdoutInteractor(memory_root=str(self.memory_dir / "stdout")),
            "say": SayInteractor(spaces_root=str(self.memory_dir / "spaces")),
            "name": NameInteractor(),
            "wake": WakeInteractor(
                memory_root=str(self.memory_dir / "wake"),
                listen=listen,
                spaces_root=str(self.memory_dir / "spaces")
            ),
            "spawn": SpawnInteractor(),
            "up": UpInteractor(),
            "incoming": IncomingInteractor(
                spaces_root=str(self.memory_dir / "spaces"),
                state_root=str(self.memory_dir / "incoming")
            ),
            "listen": listen,
        }

    def _build_transformer(self):
        """Build FIFO transformer for I/O."""
        return FifoManager()

    async def start(self, max_ticks: Optional[int] = None):
        """
        Start O.

        Args:
            max_ticks: Stop after N ticks (None = run forever)
        """
        # Validate configuration
        if self.tick_interval <= 0:
            raise ValueError(f"tick_interval must be positive, got {self.tick_interval}")

        # Ensure directories exist
        try:
            self.state_dir.mkdir(parents=True, exist_ok=True)
            self.memory_dir.mkdir(parents=True, exist_ok=True)
            (self.memory_dir / "stdout").mkdir(exist_ok=True)
            (self.memory_dir / "spaces").mkdir(exist_ok=True)
        except OSError as e:
            print(f"ERROR: Failed to create directories: {e}", file=sys.stderr)
            raise

        # Build components with error handling
        try:
            interactors = self._build_interactors()
            mind = Mind(interactors)
            state = SystemState(tick=0, executions=[])
            transformer = self._build_transformer()

            self.body = Body(
                mind=mind,
                state=state,
                transformer=transformer,
                tick_interval=self.tick_interval
            )

            # Wire body and mind references to interactors that need them
            for interactor in interactors.values():
                if hasattr(interactor, 'body'):
                    interactor.body = self.body
                if hasattr(interactor, 'mind'):
                    interactor.mind = mind

            # Bootstrap @root entity
            self.body.entity_spaces["@root"] = set()
            transformer.ensure_entity_fifos("@root")
            print("Spawned @root")

        except Exception as e:
            print(f"ERROR: Failed to initialize components: {e}", file=sys.stderr)
            raise

        # Setup signal handlers (cross-platform)
        self._shutdown_event = asyncio.Event()

        # Only use signal handlers on Unix-like systems
        if sys.platform != 'win32':
            try:
                loop = asyncio.get_event_loop()
                for sig in (signal.SIGINT, signal.SIGTERM):
                    loop.add_signal_handler(sig, self._handle_shutdown)
            except NotImplementedError:
                # Fall back to KeyboardInterrupt handling on platforms without signal support
                pass

        print(f"O starting (tick interval: {self.tick_interval}s)")
        print(f"State dir: {self.state_dir}")
        print(f"Memory dir: {self.memory_dir}")
        print("Press Ctrl+C to stop\n")

        # Run until shutdown or max_ticks
        try:
            if max_ticks:
                await self.body.run(max_ticks=max_ticks)
            else:
                # Run until shutdown signal
                run_task = asyncio.create_task(self.body.run())
                try:
                    await self._shutdown_event.wait()
                except KeyboardInterrupt:
                    # Handle Ctrl+C on Windows or when signal handlers aren't available
                    print("\nShutdown requested...")

                self.body.stop()

                # Wait for run_task to complete with timeout
                try:
                    await asyncio.wait_for(run_task, timeout=5.0)
                except asyncio.TimeoutError:
                    print("WARNING: Body.run() did not complete within 5s, cancelling...", file=sys.stderr)
                    run_task.cancel()
                    try:
                        await run_task
                    except asyncio.CancelledError:
                        pass
        except KeyboardInterrupt:
            # Handle Ctrl+C during max_ticks run
            print("\nShutdown requested...")
            if self.body:
                self.body.stop()
        except Exception as e:
            print(f"\nERROR during execution: {e}", file=sys.stderr)
            if self.body:
                self.body.stop()
            raise

        print("\nO stopped")

    def _handle_shutdown(self):
        """Handle shutdown signal."""
        print("\nShutdown requested...")
        if self._shutdown_event:
            self._shutdown_event.set()


def main():
    """Entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Run O")
    parser.add_argument(
        "--tick-interval", "-t",
        type=float,
        default=1.0,
        help="Seconds between ticks (default: 1.0)"
    )
    parser.add_argument(
        "--max-ticks", "-n",
        type=int,
        default=None,
        help="Stop after N ticks (default: run forever)"
    )
    parser.add_argument(
        "--state-dir",
        type=Path,
        default=None,
        help="State directory (default: ./state)"
    )
    parser.add_argument(
        "--memory-dir",
        type=Path,
        default=None,
        help="Memory directory (default: ./memory)"
    )
    args = parser.parse_args()

    app = App(
        tick_interval=args.tick_interval,
        state_dir=args.state_dir,
        memory_dir=args.memory_dir
    )

    asyncio.run(app.start(max_ticks=args.max_ticks))


if __name__ == "__main__":
    main()
