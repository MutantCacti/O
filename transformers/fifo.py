"""
FIFO Transformer - The fundamental I/O primitive for O.

External programs (human, LLM, other O instances) write commands to entity FIFOs.
Body reads and executes. This is the basic substrate.

Structure:
    fifos/
      @alice/
        input.fifo   # External writes, O reads
        output.fifo  # O writes, external reads
"""

import asyncio
import json
import os
import select
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional


class FifoManager:
    """
    Manages per-entity FIFO pairs.

    This is the transformer interface - Body polls this for commands.
    """

    # Maximum command size (bytes)
    MAX_COMMAND_SIZE = 65536  # 64KB

    def __init__(self, fifo_root: str = "transformers/fifos"):
        """
        Initialize FIFO manager.

        Args:
            fifo_root: Root directory for entity FIFOs
        """
        self.fifo_root = Path(fifo_root)
        self._input_fds = {}  # entity -> file descriptor
        self._output_fds = {}  # entity -> file descriptor
        self._input_buffers = {}  # entity -> accumulated bytes
        self._output_buffer = {}  # entity -> list of pending output bytes

    def _validate_entity(self, entity: str) -> None:
        """
        Validate entity name format.

        Args:
            entity: Entity name

        Raises:
            ValueError: If entity name is invalid
        """
        if not entity:
            raise ValueError("Entity name cannot be empty")
        if not entity.startswith("@"):
            raise ValueError(f"Entity name must start with @, got: {entity}")
        if len(entity) < 2:
            raise ValueError("Entity name must have at least one character after @")
        # Allow alphanumeric, hyphen, underscore after @
        name = entity[1:]
        if not all(c.isalnum() or c in "-_" for c in name):
            raise ValueError(f"Entity name contains invalid characters: {entity}")

    def ensure_entity_fifos(self, entity: str) -> None:
        """
        Create input/output FIFOs for entity if they don't exist.

        Args:
            entity: Entity name (e.g., "@alice")

        Raises:
            ValueError: If entity name is invalid
        """
        self._validate_entity(entity)

        entity_dir = self.fifo_root / entity
        entity_dir.mkdir(parents=True, exist_ok=True)

        input_path = entity_dir / "input.fifo"
        output_path = entity_dir / "output.fifo"

        if not input_path.exists():
            os.mkfifo(input_path)
        if not output_path.exists():
            os.mkfifo(output_path)

    def _cleanup_stale_fds(self, active_entities: List[str]) -> None:
        """
        Close file descriptors for entities that no longer exist.

        Args:
            active_entities: List of currently active entity names
        """
        active_set = set(active_entities)

        # Clean input FDs
        stale_input = [e for e in self._input_fds if e not in active_set]
        for entity in stale_input:
            self._close_entity_input(entity)

        # Clean output FDs
        stale_output = [e for e in self._output_fds if e not in active_set]
        for entity in stale_output:
            self._close_entity_output(entity)

    def _close_entity_input(self, entity: str) -> None:
        """Close input FD for entity."""
        if entity in self._input_fds:
            try:
                os.close(self._input_fds[entity])
            except OSError:
                pass
            del self._input_fds[entity]
        if entity in self._input_buffers:
            del self._input_buffers[entity]

    def _close_entity_output(self, entity: str) -> None:
        """Close output FD for entity."""
        if entity in self._output_fds:
            try:
                os.close(self._output_fds[entity])
            except OSError:
                pass
            del self._output_fds[entity]

    def _open_input(self, entity: str) -> Optional[int]:
        """
        Open input FIFO for entity, handling errors.

        Returns:
            File descriptor, or None if failed
        """
        if entity in self._input_fds:
            return self._input_fds[entity]

        input_path = self.fifo_root / entity / "input.fifo"
        if not input_path.exists():
            return None

        try:
            fd = os.open(str(input_path), os.O_RDONLY | os.O_NONBLOCK)
            self._input_fds[entity] = fd
            return fd
        except OSError:
            return None

    async def read_command(self, entity: str) -> Optional[str]:
        """
        Non-blocking read from entity's input FIFO.

        Buffers partial reads until a complete command (newline-terminated) is received.
        Commands are limited to MAX_COMMAND_SIZE bytes.

        Args:
            entity: Entity name

        Returns:
            Command string if available, None otherwise
        """
        fd = self._open_input(entity)
        if fd is None:
            return None

        # Check if data available using select (0 timeout = non-blocking)
        try:
            readable, _, _ = select.select([fd], [], [], 0)
            if not readable:
                # Check buffer for complete command
                return self._extract_command_from_buffer(entity)

            # Read available data
            data = os.read(fd, 4096)
            if not data:
                # EOF - FIFO closed by writer, reopen next time
                self._close_entity_input(entity)
                return self._extract_command_from_buffer(entity)

            # Append to buffer
            if entity not in self._input_buffers:
                self._input_buffers[entity] = b""
            self._input_buffers[entity] += data

            # Prevent buffer overflow - clear entirely to resync
            if len(self._input_buffers[entity]) > self.MAX_COMMAND_SIZE:
                # Keeping tail would corrupt commands; clear to resync
                self._input_buffers[entity] = b""

            return self._extract_command_from_buffer(entity)

        except OSError:
            # FD is broken, close and retry next time
            self._close_entity_input(entity)
            return None

    def _extract_command_from_buffer(self, entity: str) -> Optional[str]:
        """
        Extract first complete command from entity's buffer.

        Uses the grammar parser to determine when a complete, valid command
        has been received. Handles multiple commands in buffer by finding
        the first valid command boundary.

        Returns:
            Command string if complete command found, None otherwise
        """
        if entity not in self._input_buffers:
            return None

        buffer = self._input_buffers[entity]

        try:
            text = buffer.decode('utf-8')
        except UnicodeDecodeError:
            # Skip malformed data - clear buffer
            self._input_buffers[entity] = b""
            return None

        if not text.strip():
            return None

        # Try to parse as a command using the grammar
        from grammar.parser import parse, ParserError

        # Find all potential command boundaries (--- followed by whitespace/newline)
        # Try parsing up to each one to find first complete command
        pos = 0
        while True:
            # Find next --- terminator
            idx = text.find('---', pos)
            if idx == -1:
                # No terminator found - need more data
                return None

            # Try parsing up to this terminator (include the ---)
            end_pos = idx + 3
            # Skip any trailing whitespace/newline after ---
            while end_pos < len(text) and text[end_pos] in ' \t\n':
                end_pos += 1

            candidate = text[:idx + 3].strip()

            try:
                parse(candidate)
                # Parsing succeeded - extract this command
                self._input_buffers[entity] = text[end_pos:].encode('utf-8')
                return candidate
            except ParserError:
                # This --- wasn't a valid command end, try next one
                pos = idx + 3
                continue

    async def write_output(self, entity: str, output: dict) -> None:
        """
        Write execution result to entity's output FIFO.

        Uses blocking open with retry to ensure output is delivered.

        Args:
            entity: Entity name
            output: Result dict (will be JSON-encoded)
        """
        import select

        output_path = self.fifo_root / entity / "output.fifo"

        if not output_path.exists():
            return

        # Add timestamp
        output["timestamp"] = datetime.now(timezone.utc).isoformat()
        line = json.dumps(output) + "\n"
        data = line.encode('utf-8')

        # Try to get/open file descriptor
        max_retries = 10
        retry_delay = 0.1

        for attempt in range(max_retries):
            try:
                # Open in non-blocking mode first to check if reader exists
                if entity not in self._output_fds:
                    fd = os.open(str(output_path), os.O_WRONLY | os.O_NONBLOCK)
                    self._output_fds[entity] = fd

                fd = self._output_fds[entity]

                # Use select to wait for FIFO to be writable (reader connected)
                _, writable, _ = select.select([], [fd], [], 0.5)

                if writable:
                    os.write(fd, data)
                    return  # Success
                else:
                    # No reader yet, wait and retry
                    await asyncio.sleep(retry_delay)

            except OSError:
                # FD broken or no reader - close and retry
                self._close_entity_output(entity)
                await asyncio.sleep(retry_delay)

        # If we get here, we failed to write after all retries
        # Buffer the output for later delivery
        if entity not in self._output_buffer:
            self._output_buffer[entity] = []
        self._output_buffer[entity].append(data)

    def close(self) -> None:
        """Close all open file descriptors."""
        for entity in list(self._input_fds.keys()):
            self._close_entity_input(entity)
        for entity in list(self._output_fds.keys()):
            self._close_entity_output(entity)

    def __del__(self):
        self.close()
