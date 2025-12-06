"""
Stdout interactor - Memory persistence layer.

\\stdout write: My log entry ---
\\stdout read: last 10 ---

The first persistence: Stdout enables memory across time.

Entities can write to their own stdout stream and read it back.
This creates the foundation for state reconstruction.
"""

from grammar.parser import Command, Text, Entity, Space
from interactors.base import Interactor
from pathlib import Path
import json
from datetime import datetime, UTC


class StdoutInteractor(Interactor):
    """
    Write and read entity stdout (execution output log).

    This is the persistence layer - entities can write logs
    and query them later for state reconstruction.
    """

    def __init__(self, body=None, memory_root="memory/stdout"):
        """
        Create stdout interactor.

        Args:
            body: Body instance (for tick access)
            memory_root: Where to store stdout files
        """
        self.body = body
        self.memory_root = Path(memory_root)
        self.memory_root.mkdir(parents=True, exist_ok=True)

    def execute(self, cmd: Command, executor: str = None) -> str:
        """
        Execute stdout command (write or read).

        Args:
            cmd: Parsed command tree
            executor: Who is executing

        Returns:
            Status message or query results

        Examples:
            \\stdout write: Log entry here ---
            \\stdout read: last 10 ---
        """
        if not executor:
            return "ERROR: Stdout requires executor context"

        # Extract operation and reconstruct full content from all nodes
        # Format: "stdout write: content" or "stdout read: params"
        operation = None
        content_text = ""

        # First, reconstruct the full command text from all nodes
        full_text_parts = []
        for node in cmd.content:
            if isinstance(node, Text):
                full_text_parts.append(node.text)
            elif isinstance(node, Entity):
                full_text_parts.append(f"@{node.name}")
            elif isinstance(node, Space):
                full_text_parts.append(f"#{node.name}")

        full_text = "".join(full_text_parts).strip()

        # Parse operation from the full text
        # Format: "stdout OPERATION: content" or "stdout content"
        # Edge case: "\stdout ---" gives full_text="stdout" (just the command name)
        if full_text.lower() == "stdout":
            return "ERROR: No content to write. Usage: \\stdout CONTENT --- or \\stdout write: CONTENT ---"

        # Known operations
        OPERATIONS = {"write", "read", "query", "help", "between"}

        if ":" in full_text:
            parts = full_text.split(":", 1)
            # parts[0] = "stdout write" or "stdout read" or "stdout something"
            # parts[1] = content/params
            op_part = parts[0].strip().lower()

            # Check if the first word is an operation
            if "write" in op_part:
                operation = "write"
                content_text = parts[1].strip()
            elif "read" in op_part:
                operation = "read"
                content_text = parts[1].strip()
            elif "query" in op_part:
                operation = "query"
                content_text = parts[1].strip()
            elif "help" in op_part:
                operation = "help"
                content_text = parts[1].strip()
            elif "between" in op_part:
                operation = "between"
                content_text = parts[1].strip()
            else:
                # Colon exists but no recognized operation keyword before it
                # Check if they tried something like "\stdout find:" or "\stdout clear:"
                # (first word after stdout, excluding "stdout" itself)
                attempted = op_part.replace("stdout", "").strip()
                # If it looks like an operation attempt (single word before colon)
                if attempted and " " not in attempted and attempted not in OPERATIONS:
                    return f"ERROR: Unknown operation '{attempted}:'. Available: write, read, between, query, help. Try: \\stdout help: ---"
                else:
                    # Colon in content (like "time is 23:21")
                    operation = "write"
                    content_text = full_text
        else:
            # No colon, treat entire text as write content
            operation = "write"
            content_text = full_text

        if not operation:
            operation = "write"  # Default to write

        # Route to appropriate handler
        if operation == "write":
            return self._write(executor, content_text)
        elif operation == "read":
            return self._read(executor, content_text)
        elif operation == "between":
            return self._between(executor, content_text)
        elif operation == "query":
            return self._query(executor, content_text)
        elif operation == "help":
            return self._help(content_text)
        else:
            return f"ERROR: Unknown operation '{operation}'. Use: write, read, between, query, help"

    def _write(self, entity: str, content: str) -> str:
        """Write entry to entity's stdout."""
        content = content.strip()

        if not content:
            return "ERROR: No content to write. Usage: \\stdout write: message ---"

        # Get current tick from body
        tick = self.body.state.tick if (self.body and hasattr(self.body, 'state')) else 0

        # Create stdout entry
        entry = {
            "tick": tick,
            "entity": entity,
            "content": content,
            "timestamp": datetime.now(UTC).isoformat()
        }

        # Write to JSONL file (one JSON object per line)
        entity_file = self.memory_root / f"{entity}.jsonl"
        with open(entity_file, "a") as f:
            f.write(json.dumps(entry) + "\n")

        return f"Written to stdout (tick {tick})"

    def _read(self, entity: str, params: str) -> str:
        """Read from entity's stdout."""
        params = params.strip()

        # Default: read last 1 (most recent)
        if not params:
            n = 1
        elif params == "last 10":
            n = 10
        elif params.startswith("last "):
            try:
                n = int(params.split()[1])
            except (IndexError, ValueError):
                return "ERROR: Invalid read params. Usage: \\stdout read: last N ---"
        else:
            return f"ERROR: Unknown read pattern '{params}'. Try: last 10"

        # Read from JSONL file
        entity_file = self.memory_root / f"{entity}.jsonl"

        if not entity_file.exists():
            return f"No stdout for {entity} yet"

        # Read all lines (inefficient but simple for now)
        entries = []
        with open(entity_file, "r") as f:
            for line in f:
                entries.append(json.loads(line))

        # Get last N
        last_n = entries[-n:] if len(entries) >= n else entries

        if not last_n:
            return f"No entries in stdout for {entity}"

        # Format output
        lines = [f"Last {len(last_n)} stdout entries for {entity}:"]
        for entry in last_n:
            tick = entry.get("tick", "?")
            content = entry.get("content", "")
            lines.append(f"  [tick {tick}] {content}")

        return "\n".join(lines)

    def _between(self, entity: str, params: str) -> str:
        """Read entries between tick range."""
        params = params.strip()

        # Parse: "TICK_START TICK_END" or "TICK_START and TICK_END"
        parts = params.replace(" and ", " ").split()

        if len(parts) != 2:
            return "ERROR: Invalid between params. Usage: \\stdout between: TICK_START TICK_END ---"

        try:
            tick_start = int(parts[0])
            tick_end = int(parts[1])
        except ValueError:
            return "ERROR: Tick values must be integers. Usage: \\stdout between: TICK_START TICK_END ---"

        if tick_start > tick_end:
            return f"ERROR: Start tick ({tick_start}) must be <= end tick ({tick_end})"

        # Read from JSONL file
        entity_file = self.memory_root / f"{entity}.jsonl"

        if not entity_file.exists():
            return f"No stdout for {entity} yet"

        # Read and filter by tick range
        entries = []
        with open(entity_file, "r") as f:
            for line in f:
                entry = json.loads(line)
                tick = entry.get("tick", 0)
                if tick_start <= tick <= tick_end:
                    entries.append(entry)

        if not entries:
            return f"No entries between tick {tick_start} and {tick_end}"

        # Format output
        lines = [f"Entries between tick {tick_start} and {tick_end} for {entity}:"]
        for entry in entries:
            tick = entry.get("tick", "?")
            content = entry.get("content", "")
            lines.append(f"  [tick {tick}] {content}")

        return "\n".join(lines)

    def _query(self, entity: str, pattern: str) -> str:
        """
        Query entries by content pattern.

        NOTE: This is a temporary implementation using simple substring matching.
        Once conditions are finalized in the parser/mind, this should be updated
        to parse and evaluate proper condition expressions like:
          \\stdout query: ?(tick > 42 and content contains "error") ---

        Current implementation: case-insensitive substring match only.
        """
        pattern = pattern.strip()

        if not pattern:
            return "ERROR: No query pattern. Usage: \\stdout query: PATTERN ---"

        # Read from JSONL file
        entity_file = self.memory_root / f"{entity}.jsonl"

        if not entity_file.exists():
            return f"No stdout for {entity} yet"

        # Read and filter by pattern (case-insensitive substring match)
        entries = []
        with open(entity_file, "r") as f:
            for line in f:
                entry = json.loads(line)
                content = entry.get("content", "").lower()
                if pattern.lower() in content:
                    entries.append(entry)

        if not entries:
            return f"No entries matching '{pattern}'"

        # Format output
        lines = [f"Entries matching '{pattern}' for {entity}:"]
        for entry in entries:
            tick = entry.get("tick", "?")
            content = entry.get("content", "")
            lines.append(f"  [tick {tick}] {content}")

        return "\n".join(lines)

    def _help(self, topic: str) -> str:
        """Show help for stdout interactor."""
        topic = topic.strip().lower()

        # If specific topic requested, show detailed help for that operation
        if topic == "write":
            return """write: Persist a log entry to your stdout stream

Usage:
  \\stdout write: Your message here ---
  \\stdout Your message here ---              (implicit write)

Format:
  Appends JSONL entry to memory/stdout/@you.jsonl with:
    - tick: Current system tick
    - entity: Your entity name
    - content: Your message
    - timestamp: UTC ISO-8601

Examples:
  \\stdout write: Initialized with config A ---
  \\stdout Task X complete ---
  \\stdout Error: failed to connect to @bob ---"""

        elif topic == "read":
            return """read: Query your stdout history

Usage:
  \\stdout read: last N ---                   (last N entries)
  \\stdout read: ---                          (defaults to last 1)

Output format:
  Last N stdout entries for @you:
    [tick 42] First message
    [tick 43] Second message
    ...

Note: This is YOUR stdout only (per-entity storage).
      Basis for memory/personal. For shared memory, see memory/public.

Examples:
  \\stdout read: ---                          (most recent entry)
  \\stdout read: last 5 ---
  \\stdout read: last 20 ---

See also: between, query"""

        elif topic == "between":
            return """between: Query temporal range by tick

Usage:
  \\stdout between: TICK_START TICK_END ---
  \\stdout between: TICK_START and TICK_END ---   (natural language)

Output format:
  Entries between tick N and M for @you:
    [tick N] First message
    [tick N+1] Second message
    ...

Examples:
  \\stdout between: 10 20 ---                (ticks 10-20 inclusive)
  \\stdout between: 42 42 ---                (exactly tick 42)
  \\stdout between: 0 100 ---                (first 100 ticks)

Use cases:
  - Debugging specific time ranges
  - Analyzing what happened during an incident
  - Replaying state transitions

See also: read, query"""

        elif topic == "query":
            return """query: Search entries by content pattern

Usage:
  \\stdout query: PATTERN ---                (case-insensitive substring match)

Output format:
  Entries matching 'PATTERN' for @you:
    [tick N] Matching message
    ...

Examples:
  \\stdout query: error ---                  (find all errors)
  \\stdout query: @bob ---                   (find mentions of @bob)
  \\stdout query: failed to connect ---     (find connection issues)

Note: Currently simple substring matching. Advanced filtering (conditions,
      boolean logic, tick ranges) planned for future release.

Use cases:
  - Find all error messages
  - Locate entity mentions
  - Debug specific issues
  - Audit activity patterns

See also: read, between"""

        # Default: show general help (strace-style compression)
        return """\\stdout - Memory persistence layer for entities

Usage: \\stdout OPERATION: [ARGS] ---

Operations:
  write:    Persist log entry to your stdout stream (default if no operation)
  read:     Query stdout history (last N entries)
  between:  Query temporal range by tick (TICK_START TICK_END)
  query:    Search entries by content pattern (substring match)
  help:     Show this help or help for specific operation

Quick start:
  \\stdout write: My first log entry ---
  \\stdout My second entry ---                (implicit write)
  \\stdout read: ---                          (most recent entry)
  \\stdout read: last 10 ---                  (last 10 entries)

Storage:
  Location: memory/stdout/@entity.jsonl (PER-ENTITY storage)
  Format:   JSON Lines (one object per line, append-only)
  Fields:   tick, entity, content, timestamp
  Scope:    Private to each entity (basis for memory/personal)

State reconstruction pattern:
  1. On wake, read recent stdout: \\stdout read: last 20 ---
  2. Parse output to find: What was I doing? Who was involved? Next step?
  3. Continue from where you left off

Examples:
  \\stdout write: Started processing messages from #general ---
  \\stdout write: Processed 42 messages, found 3 mentions ---
  \\stdout read: last 5 ---

For operation-specific help:
  \\stdout help: write ---
  \\stdout help: read ---
  \\stdout help: between ---
  \\stdout help: query ---

Key concept: Interactors are stateless. Stdout is how you remember."""
