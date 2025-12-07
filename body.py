"""
body.py - The Environment Substrate

Body is the physics of O - the autonomous environment where entities exist.

It provides:
- Spatial substrate (spaces ↔ entities, the directed cyclical structure)
- Temporal substrate (tick clock, wake conditions)
- Autonomous operation (Body ticks itself - a heart beats on its own)

From theta.py: Entity = State(Is Spaces)
Body manages that "Is" - the WHERE-ing of existence.

The directed graph:
  Space → Entity (containment: space > entity)
  Entity → Space (membership: entity ∈ space)

Body exposes its data structures directly. Interactors can read/write them.
Body runs autonomously. External code just launches it.
"""

import time
from pathlib import Path
from typing import Dict, List, Optional, Set
from dataclasses import dataclass, field

from mind import Mind
from state.state import SystemState
from grammar.parser import Condition


@dataclass
class Space:
    """
    A space in the environment.

    Spaces contain entities. The directed edge: Space → Entity

    Interactors can mutate directly:
        body.spaces["#channel"].name = "general"
        body.spaces["#channel"].members.add("@alice")
    """
    name: str = ""  # Display name (mutable, set by \name interactor)
    members: Set[str] = field(default_factory=set)  # Entity IDs in this space


@dataclass
class WakeRecord:
    """
    Record of entity sleeping with wake condition.

    Entities suspend with self-prompt to remember why they're waking.

    Interactors can add to sleep queue:
        body.sleep_queue["@alice"] = WakeRecord(
            entity="@alice",
            condition=condition_node,
            self_prompt="Check what Bob said"
        )
    """
    entity: str  # Who is sleeping
    condition: Condition  # When to wake
    self_prompt: str = None  # What to remember on wake
    resume_command: str = None  # What to execute on wake (optional)


class Body:
    """
    The autonomous environment substrate.

    Body is the physics of O - it runs itself like a heart beating on its own.

    Provides:
    1. Spatial substrate - The directed cyclical structure (spaces ↔ entities)
    2. Temporal substrate - Clock ticks and wake coordination
    3. Autonomous operation - Ticks itself, executes ready entities

    Data structures are exposed directly. Interactors can read/write them:
        body.spaces["#channel"].members.add("@alice")
        body.entity_spaces["@alice"].add("#channel")
        body.sleep_queue["@bob"] = WakeRecord(...)

    Body is the grounding wire that keeps entities alive.
    """

    def __init__(self, mind: Mind, state: SystemState, transformers: List = None, tick_interval: float = 1.0):
        """
        Initialize environment.

        Args:
            mind: Execution engine (command processor)
            state: Execution log (memory)
            transformers: List of I/O devices (humans, LLMs) to poll for input
            tick_interval: Seconds between clock ticks
        """
        self.mind = mind
        self.state = state
        self.transformers = transformers or []
        self.tick_interval = tick_interval

        # ===== Spatial substrate (the directed cyclical structure) =====
        # Exposed for direct access by interactors

        # Space → Entity (containment)
        self.spaces: Dict[str, Space] = {}
        # Example: {#channel: Space(name="general", members={@alice, @bob})}

        # Entity → Space (membership)
        self.entity_spaces: Dict[str, Set[str]] = {}
        # Example: {@alice: {#channel, #dev}}

        # ===== Temporal substrate =====
        # Exposed for direct access by interactors

        self.sleep_queue: Dict[str, WakeRecord] = {}
        # Example: {@bob: WakeRecord(condition=..., self_prompt="...")}

    # ===== Temporal Coordination =====

    def _check_wake_conditions(self) -> List[WakeRecord]:
        """
        Check sleep queue for entities whose conditions are satisfied.

        Returns:
            List of wake records for entities ready to resume
        """
        ready = []

        for entity, record in list(self.sleep_queue.items()):
            if self._evaluate_condition(record.condition):
                ready.append(record)
                # Remove from sleep queue (one-shot wake)
                del self.sleep_queue[entity]

        return ready

    def _evaluate_condition(self, condition: Condition) -> bool:
        r"""
        Evaluate wake condition against environment state.

        Conditions can contain:
        - Scheduler queries: ?($(\messages #general---) > 5)
        - Response patterns: ?(response(@bob))
        - Time conditions: ?(sleep(100))
        - Boolean logic: ?(A && B)

        Args:
            condition: Condition node from grammar

        Returns:
            True if condition satisfied
        """
        # TODO: Implement condition evaluation
        # For now: stub always returns False
        #
        # Real implementation:
        # 1. Check if condition contains SchedulerQuery nodes
        # 2. If yes: evaluate queries via self.observe()
        # 3. Check for response(@entity) patterns → scan logs
        # 4. Check for sleep(N) → compare ticks elapsed
        # 5. Evaluate boolean operators
        return False

    def tick(self):
        """
        One heartbeat of the environment.

        1. Poll transformers (I/O devices) for input
        2. Check wake conditions for sleeping entities
        3. Execute entities whose conditions are satisfied
        4. Persist execution log to disk
        5. Advance clock

        This runs autonomously in the main loop.
        """
        # Poll transformers (humans, LLMs) for input
        for transformer in self.transformers:
            result = transformer.poll(self)
            if result:
                entity, command = result
                output = self.mind.execute(command, executor=entity)
                self.state.add_execution(entity, command, output)

        # Check who should wake
        ready_entities = self._check_wake_conditions()

        # Execute ready entities
        for record in ready_entities:
            # In full implementation: stdin buffer + self_prompt → entity
            # For now: just execute resume command if present
            if record.resume_command:
                output = self.mind.execute(record.resume_command, executor=record.entity)
                self.state.add_execution(record.entity, record.resume_command, output)

        # Persist execution log
        if self.state.executions:
            self.state.save_tick_log(Path("state/logs"))

        # Advance clock
        self.state.advance_tick()

    # ===== Autonomous Operation =====

    def run(self, max_ticks: Optional[int] = None):
        """
        Run the environment autonomously.

        Body ticks itself like a heart beating on its own.
        External code just launches this and lets it run.

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

    # ===== Direct Intervention =====

    def execute_now(self, entity: str, command: str) -> str:
        """
        Execute command immediately (bypass temporal layer).

        Skips sleep queue - executes command synchronously.
        This is for direct intervention in the environment.

        Use cases:
        - Human-initiated commands (web/CLI interface)
        - System bootstrap
        - Testing/debugging

        Args:
            entity: Who is executing (entity name)
            command: Command string to execute

        Returns:
            Execution output
        """
        output = self.mind.execute(command, executor=entity)
        self.state.add_execution(entity, command, output)
        return output


# Test/demo
if __name__ == '__main__':
    # Bootstrap minimal O environment
    mind = Mind(interactors={})
    state = SystemState(tick=0, executions=[])
    body = Body(mind, state, tick_interval=1.0)

    # Test immediate execution (bypass temporal layer)
    print("Testing environment...")
    output = body.execute_now("@test", r"\say #general Hello ---")
    print(f"Output: {output}")

    # Show environment state
    print(f"\nEnvironment state:")
    print(f"Tick: {state.tick}")
    print(f"Executions: {len(state.executions)}")
    print(f"Sleep queue: {len(body.sleep_queue)} entities")
    if state.executions:
        print(f"\nLast execution:")
        print(f"  Entity: {state.executions[0].executor}")
        print(f"  Command: {state.executions[0].command}")
        print(f"  Output: {state.executions[0].output}")
