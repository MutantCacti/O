r"""
Publish interactor - write output artifacts to files.

\publish report.md This is the content ---
→ Writes "This is the content" to output/report.md

\publish solutions/q1.txt Answer here ---
→ Writes to output/solutions/q1.txt

Output root is configurable, defaults to "output/".
Subdirectories are created automatically.

TEMPORARY: This writes to local files. Future versions will publish
to memory/public (async database).
"""

import json
from pathlib import Path
from datetime import datetime, timezone
from grammar.parser import Command, Text, Entity, Space
from interactors.base import Interactor


class PublishInteractor(Interactor):
    r"""
    Write content to output files.

    \publish filename content ---

    First text token is filename, rest is content.
    Filename can include subdirectories (e.g., "solutions/q1.md").
    """

    def __init__(self, body=None, output_root: str = "output"):
        """
        Create publish interactor.

        Args:
            body: Body instance (for state access)
            output_root: Root directory for output files
        """
        self.body = body
        self.output_root = Path(output_root)
        self.output_root.mkdir(parents=True, exist_ok=True)

    def _sanitize_path(self, filename: str) -> Path | None:
        """
        Sanitize and validate filename.

        Prevents path traversal attacks.

        Args:
            filename: Requested filename

        Returns:
            Safe absolute path, or None if invalid
        """
        # Remove leading/trailing whitespace
        filename = filename.strip()

        if not filename:
            return None

        # Block absolute paths
        if filename.startswith("/"):
            return None

        # Remove leading slashes after check (for normalization)
        filename = filename.lstrip("/")

        if not filename:
            return None

        # Resolve to catch ../ attacks
        target = (self.output_root / filename).resolve()

        # Must be under output_root
        try:
            target.relative_to(self.output_root.resolve())
        except ValueError:
            return None

        return target

    def execute(self, cmd: Command, executor: str = None) -> str:
        """
        Publish content to file.

        Args:
            cmd: Parsed command with filename and content
            executor: Entity publishing

        Returns:
            Confirmation or error message
        """
        # Extract text content
        text_parts = []
        for node in cmd.content:
            if isinstance(node, Text):
                text_parts.append(node.text)

        full_text = " ".join(text_parts).strip()

        if not full_text:
            return r"ERROR: No content. Usage: \publish filename content ---"

        # Split into filename and content
        # First whitespace-separated token is filename
        parts = full_text.split(None, 1)

        if len(parts) < 2:
            return r"ERROR: Need filename and content. Usage: \publish filename content ---"

        filename = parts[0]
        content = parts[1]

        # Sanitize path
        target = self._sanitize_path(filename)
        if target is None:
            return f"ERROR: Invalid filename: {filename}"

        # Create parent directories
        target.parent.mkdir(parents=True, exist_ok=True)

        # Write content
        try:
            # Append mode for incremental writing
            mode = "a" if target.exists() else "w"

            with open(target, mode) as f:
                f.write(content)
                # Add newline if content doesn't end with one
                if not content.endswith("\n"):
                    f.write("\n")

            # Get tick for logging
            tick = self.body.state.tick if (self.body and hasattr(self.body, 'state')) else 0

            return f"Published to {filename} (tick {tick})"

        except OSError as e:
            return f"ERROR: Failed to write {filename}: {e}"

    def read_file(self, filename: str) -> str | None:
        """
        Read a published file.

        Convenience method for agents to read their own output.

        Args:
            filename: File to read

        Returns:
            File contents, or None if not found
        """
        target = self._sanitize_path(filename)
        if target is None or not target.exists():
            return None

        try:
            with open(target) as f:
                return f.read()
        except OSError:
            return None
