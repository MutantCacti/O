"""
body.py - The grounding wire

Polls mind in ticks, checks wake conditions, executes ready entities.
This is the main loop that keeps O alive.
"""

import time
from pathlib import Path
from typing import List, Tuple

from mind import Mind
from state.state import SystemState
from grammar.parser import parse, Condition, Text


class Body:
    """
    The grounding wire / main loop.

    Polls wake conditions, executes ready entities, advances time.
    """

    def __init__(self, mind: Mind, state: SystemState, tick_interval: float = 1.0):
        """
        Create body.

        Args:
            mind: The execution engine
            state: State observer
            tick_interval: Seconds between ticks
        """
        self.mind = mind
        self.state = state
        self.tick_interval = tick_interval
        self.wake_registry = {}  # {entity: (condition_str, queued_command)}

    def register_wake(self, entity: str, condition_str: str, queued_command: str = None):
        """
        Register entity to wake when condition satisfied.

        Args:
            entity: Entity name
            condition_str: Condition expression (for now, just store as string)
            queued_command: Command to execute on wake (None = just wake)
        """
        self.wake_registry[entity] = (condition_str, queued_command)

    def check_wake_conditions(self) -> List[Tuple[str, str]]:
        """
        Check all wake conditions, return ready entities.

        Returns:
            List of (entity, command) tuples ready to execute
        """
        ready = []

        for entity, (condition_str, queued_command) in list(self.wake_registry.items()):
            # For now: simple condition checking
            # TODO: Proper condition evaluation from Condition nodes

            if self._evaluate_condition(condition_str):
                # Entity is ready
                if queued_command:
                    ready.append((entity, queued_command))

                # Remove from registry (one-shot wake)
                del self.wake_registry[entity]

        return ready

    def _evaluate_condition(self, condition_str: str) -> bool:
        """
        Evaluate a condition string against current state.

        For now: stub implementation.
        Real implementation would parse Condition node and evaluate.

        Args:
            condition_str: String representation of condition

        Returns:
            True if condition satisfied
        """
        # Stub: always return False for now
        # Real implementation would:
        # 1. Parse condition to Condition node
        # 2. Check for response(@entity) in recent logs
        # 3. Check for sleep(N) elapsed time
        # 4. Evaluate boolean logic
        return False

    def tick(self):
        """
        Execute one tick:
        1. Check wake conditions
        2. Execute ready entities
        3. Save logs
        4. Advance time
        """
        # Check for ready entities
        ready = self.check_wake_conditions()

        # Execute each ready entity
        for entity, command in ready:
            output = self.mind.execute(command)
            self.state.add_execution(entity, command, output)

        # Save this tick's log
        if self.state.executions:  # Only save if something happened
            self.state.save_tick_log(Path("state/logs"))

        # Advance to next tick
        self.state.advance_tick()

    def run(self, max_ticks: int = None):
        """
        Main loop: tick forever (or until max_ticks).

        Args:
            max_ticks: Stop after N ticks (None = run forever)
        """
        ticks = 0

        while True:
            self.tick()

            ticks += 1
            if max_ticks and ticks >= max_ticks:
                break

            time.sleep(self.tick_interval)

    def execute_now(self, entity: str, command: str) -> str:
        """
        Execute command immediately (bypass wake system).

        Useful for:
        - Manual command injection
        - Human interface
        - Bootstrap initialization

        Args:
            entity: Executor
            command: Command string

        Returns:
            Output from execution
        """
        output = self.mind.execute(command)
        self.state.add_execution(entity, command, output)
        return output


# Simple test/demo
if __name__ == '__main__':
    # Create minimal system
    mind = Mind(interactors={})  # No interactors yet
    state = SystemState(tick=0, executions=[])
    body = Body(mind, state, tick_interval=1.0)

    # Try to execute a command (will fail - no interactors)
    print("Executing test command...")
    output = body.execute_now("@test", r"\say #general Hello ---")
    print(f"Output: {output}")

    # Show state
    print(f"\nState after execution:")
    print(f"Tick: {state.tick}")
    print(f"Executions: {len(state.executions)}")
    if state.executions:
        print(f"  {state.executions[0].executor}: {state.executions[0].command}")
        print(f"  Output: {state.executions[0].output}")
