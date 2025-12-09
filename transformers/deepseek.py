r"""
DeepSeek Transformer - LLM-driven agent reasoning.

This transformer runs OUTSIDE the O tick loop. It:
1. Watches entity output FIFOs for execution results
2. Builds context from results + entity state
3. Calls DeepSeek API to decide next action
4. Writes command to entity input FIFO

Usage:
    python -m transformers.deepseek @solver

The transformer is per-entity. Run multiple instances for multiple agents.
This is intentional - each agent has its own reasoning loop.

TEMPORARY: This is a minimal implementation for Camp 2 testing.
"""

import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# Load .env file if python-dotenv is available
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

try:
    from openai import AsyncOpenAI
except ImportError:
    AsyncOpenAI = None


class DeepSeekTransformer:
    """
    LLM-driven transformer for a single entity.

    Runs an async loop:
    1. Read from output.fifo (O's execution results)
    2. Build prompt with context
    3. Call DeepSeek
    4. Write command to input.fifo
    """

    def __init__(
        self,
        entity: str,
        fifo_root: str = "transformers/fifos",
        model: str = "deepseek-chat",
        api_key: Optional[str] = None,
        system_prompt: Optional[str] = None,
    ):
        """
        Initialize transformer for entity.

        Args:
            entity: Entity name (e.g., "@solver")
            fifo_root: Root directory for FIFOs
            model: DeepSeek model to use
            api_key: DeepSeek API key (or from DEEPSEEK_API_KEY env)
            system_prompt: Override default system prompt
        """
        if AsyncOpenAI is None:
            raise ImportError("openai package required: pip install openai")

        self.entity = entity
        self.fifo_root = Path(fifo_root)
        self.model = model

        # API client
        api_key = api_key or os.environ.get("DEEPSEEK_API_KEY")
        if not api_key:
            raise ValueError("DEEPSEEK_API_KEY required")

        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url="https://api.deepseek.com"
        )

        # Context accumulator
        self.history = []  # List of {role, content} messages
        self.max_history = 20  # Keep last N exchanges

        # System prompt
        self.system_prompt = system_prompt or self._default_system_prompt()

    def _default_system_prompt(self) -> str:
        """Default system prompt for O agents."""
        return rf"""You are {self.entity}, an autonomous agent in O.

O is a distributed system where entities communicate through spaces.

SPACES:
- #general, #dev, etc. are named spaces (channels). Must exist before sending.
- @alice-@bob is an entity-addressed space (auto-created when entities message each other)
- You join spaces by listening to them, then can read messages from them.

COMMANDS (all end with ---):

Communication:
- \say @bob Hello! --- : Send DM to @bob (creates @{self.entity}-@bob space)
- \say #general Hello! --- : Send to named space (must be member)
- \say @(alice, bob) Hi both --- : Send to multiple entities
- \listen @bob --- : Subscribe to messages from @bob
- \listen #general --- : Subscribe to a named space
- \read --- : Read all unread messages from subscribed spaces
- \read @bob --- : Read only messages from @bob
- \incoming --- : Check if you have new messages (returns "true" or "false")

Output:
- \publish report.md Your content here --- : Write to output/report.md
- \publish solutions/q1.txt Answer --- : Creates subdirectories as needed

Entity management:
- \spawn @helper --- : Create a new entity
- \name @me Alice --- : Set display name (not implemented yet)

Control flow:
- \wake ?(condition) prompt --- : Sleep until condition is true, then wake with prompt
- \eval ?(true or false) --- : Evaluate boolean condition
- \eval ?($(\incoming---)) --- : Evaluate with nested command
- \eval ?(10 > 5) --- : Comparison operators: <, >, =

Utility:
- \echo text --- : Echo text back
- \up --- : Health check, returns "true"

CONDITIONS in ?():
- Literals: true, false
- Boolean: and, or, not (infix operators)
- Comparisons: <, >, =
- Commands: $(\command---) executes and uses result

WORKFLOW:
1. You receive the result of each command you issue
2. Use \publish to write your work incrementally
3. Use \read to check messages from collaborators
4. Respond with exactly ONE command per turn

You are autonomous. Solve problems step by step. Write your reasoning to scratch files if needed.
"""

    async def read_output(self, timeout: float = 30.0) -> Optional[dict]:
        """
        Read next output from entity's output.fifo.

        Uses non-blocking I/O with polling to avoid hanging indefinitely.

        Args:
            timeout: Maximum seconds to wait for output

        Returns:
            Parsed JSON output dict, or None on timeout/error
        """
        import select

        output_path = self.fifo_root / self.entity / "output.fifo"

        if not output_path.exists():
            return None

        # Open non-blocking
        try:
            fd = os.open(str(output_path), os.O_RDONLY | os.O_NONBLOCK)
        except OSError as e:
            print(f"[{self.entity}] FIFO open error: {e}", file=sys.stderr)
            return None

        try:
            # Poll with timeout
            elapsed = 0.0
            poll_interval = 0.1
            buffer = b""

            while elapsed < timeout:
                readable, _, _ = select.select([fd], [], [], poll_interval)

                if readable:
                    try:
                        data = os.read(fd, 4096)
                        if not data:
                            # EOF - writer closed, check buffer
                            break
                        buffer += data
                        # Check for complete line
                        if b'\n' in buffer:
                            line, _ = buffer.split(b'\n', 1)
                            return json.loads(line.decode('utf-8').strip())
                    except OSError:
                        break

                elapsed += poll_interval
                await asyncio.sleep(0)  # Yield to event loop

            # Check buffer one last time
            if buffer:
                try:
                    return json.loads(buffer.decode('utf-8').strip())
                except json.JSONDecodeError:
                    pass

        except Exception as e:
            print(f"[{self.entity}] Read error: {e}", file=sys.stderr)
        finally:
            try:
                os.close(fd)
            except OSError:
                pass

        return None

    async def write_command(self, command: str) -> bool:
        """
        Write command to entity's input.fifo.

        Args:
            command: Command string to write

        Returns:
            True if successful
        """
        input_path = self.fifo_root / self.entity / "input.fifo"

        if not input_path.exists():
            return False

        try:
            with open(input_path, "w") as f:
                f.write(command.strip() + "\n")
            return True
        except OSError as e:
            print(f"[{self.entity}] Write error: {e}", file=sys.stderr)
            return False

    async def think(self, last_output: Optional[dict] = None) -> str:
        """
        Call DeepSeek to decide next action.

        Args:
            last_output: Most recent execution result (if any)

        Returns:
            Command string to execute
        """
        # Build user message from last output
        if last_output:
            user_content = f"Command: {last_output.get('command', '?')}\nResult: {last_output.get('output', '?')}"
            self.history.append({"role": "user", "content": user_content})

        # Trim history
        if len(self.history) > self.max_history:
            self.history = self.history[-self.max_history:]

        # Build messages
        messages = [{"role": "system", "content": self.system_prompt}]
        messages.extend(self.history)

        # If no history yet, add initial prompt
        if not self.history:
            messages.append({
                "role": "user",
                "content": "You have just been spawned. What is your first action?"
            })

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=500,
                temperature=0.7,
            )

            raw_response = response.choices[0].message.content.strip()

            # Extract command - find first backslash command in response
            # LLMs often include explanatory text before the actual command
            command = raw_response
            if '\\' in raw_response:
                # Find the first backslash that starts a command
                idx = raw_response.find('\\')
                if idx > 0:
                    # There's text before the command - extract just the command
                    command = raw_response[idx:]

            # Ensure command ends with --- (LLMs sometimes forget)
            if command.startswith('\\') and not command.rstrip().endswith('---'):
                command = command.rstrip() + ' ---'

            # Record full response in history for context
            self.history.append({"role": "assistant", "content": raw_response})

            return command

        except Exception as e:
            print(f"[{self.entity}] API error: {e}", file=sys.stderr)
            # Fallback: echo error
            return r"\echo API error, retrying ---"

    async def run(self, initial_prompt: Optional[str] = None):
        """
        Main loop: read output → think → write command.

        Args:
            initial_prompt: Optional initial context to add to history
        """
        print(f"[{self.entity}] Starting transformer loop", file=sys.stderr)

        # Add initial prompt to history if provided
        if initial_prompt:
            self.history.append({"role": "user", "content": initial_prompt})

        # Initial action (no prior output)
        command = await self.think()
        print(f"[{self.entity}] → {command}", file=sys.stderr)
        await self.write_command(command)

        # Main loop
        while True:
            # Wait for O to execute and write output
            output = await self.read_output()

            if output is None:
                # FIFO closed or error, wait and retry
                await asyncio.sleep(0.5)
                continue

            print(f"[{self.entity}] ← {output.get('output', '?')[:100]}", file=sys.stderr)

            # Think and act
            command = await self.think(output)
            print(f"[{self.entity}] → {command}", file=sys.stderr)

            # Check for termination commands
            if command.lower() in ["done", "exit", "quit", r"\quit ---"]:
                print(f"[{self.entity}] Terminating", file=sys.stderr)
                break

            await self.write_command(command)


async def main():
    """CLI entry point."""
    if len(sys.argv) < 2:
        print("Usage: python -m transformers.deepseek @entity [initial_prompt]", file=sys.stderr)
        sys.exit(1)

    entity = sys.argv[1]
    initial_prompt = " ".join(sys.argv[2:]) if len(sys.argv) > 2 else None

    transformer = DeepSeekTransformer(entity)
    await transformer.run(initial_prompt)


if __name__ == "__main__":
    asyncio.run(main())
