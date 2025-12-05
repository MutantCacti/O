"""
O State System

State is the append-only log of command executions.
Each execution records: tick, executor, command tree, output.

No derived views. No classification. Just what happened.

The four logical behaviors (Closed, Open, DepthLimit, Split)
emerge from interpreting the command and output, not from
explicit status fields.
"""

from dataclasses import dataclass, asdict
from typing import List, Optional
from pathlib import Path
import json
import sys
sys.path.append(str(Path(__file__).parent.parent))

from grammar.parser import Command, parse


@dataclass
class ExecutionRecord:
    """
    A single command execution.

    Primitives:
    - tick: When this happened (discrete time)
    - executor: Who executed this (entity name)
    - command: What was intended (parsed Command tree)
    - output: What happened (stdout/stderr combined)
    """
    tick: int
    executor: str
    command: Command
    output: str

    def to_dict(self) -> dict:
        """Serialize to JSON-compatible dict"""
        return {
            "tick": self.tick,
            "executor": self.executor,
            "command": self._serialize_command(self.command),
            "output": self.output
        }

    @staticmethod
    def _serialize_command(cmd: Command) -> dict:
        """Serialize Command tree to dict"""
        return {
            "type": "Command",
            "content": [
                {
                    "type": node.__class__.__name__,
                    "value": str(node)
                }
                for node in cmd.content
            ]
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'ExecutionRecord':
        """Deserialize from JSON dict"""
        # For now, reconstruct command by re-parsing
        # TODO: Full Command deserialization
        command_str = cls._reconstruct_command_str(data["command"])
        command = parse(command_str)

        return cls(
            tick=data["tick"],
            executor=data["executor"],
            command=command,
            output=data["output"]
        )

    @staticmethod
    def _reconstruct_command_str(cmd_dict: dict) -> str:
        """Reconstruct command string from serialized dict"""
        # Simple reconstruction for now
        parts = []
        for node in cmd_dict["content"]:
            parts.append(node["value"])
        return "\\" + " ".join(parts) + " ---"


@dataclass
class SystemState:
    """
    Current state of the O system.

    State is just the append-only execution log.
    Everything else (entity budgets, space membership, wake conditions)
    is derived by scanning this log.
    """
    tick: int
    executions: List[ExecutionRecord]

    def add_execution(self, executor: str, command: Command, output: str):
        """Record a new command execution"""
        record = ExecutionRecord(
            tick=self.tick,
            executor=executor,
            command=command,
            output=output
        )
        self.executions.append(record)

    def save_tick_log(self, log_dir: Path):
        """Save this tick's executions to logs/log_TIME.json"""
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / f"log_{self.tick}.json"

        data = {
            "tick": self.tick,
            "executions": [e.to_dict() for e in self.executions]
        }

        with open(log_path, 'w') as f:
            json.dump(data, f, indent=2)

    def save_state(self, state_path: Path):
        """Save current state to state.json"""
        data = {
            "tick": self.tick,
            "executions": [e.to_dict() for e in self.executions]
        }

        with open(state_path, 'w') as f:
            json.dump(data, f, indent=2)

    @classmethod
    def load_state(cls, state_path: Path) -> 'SystemState':
        """Load state from state.json"""
        with open(state_path) as f:
            data = json.load(f)

        executions = [
            ExecutionRecord.from_dict(e)
            for e in data["executions"]
        ]

        return cls(
            tick=data["tick"],
            executions=executions
        )

    @classmethod
    def load_tick_log(cls, log_path: Path) -> List[ExecutionRecord]:
        """Load a specific tick log"""
        with open(log_path) as f:
            data = json.load(f)

        return [
            ExecutionRecord.from_dict(e)
            for e in data["executions"]
        ]

    def advance_tick(self):
        """Move to next tick, clear execution buffer"""
        self.tick += 1
        self.executions = []


# Utility functions for deriving information from execution logs

def reconstruct_entity_executions(
    logs: List[ExecutionRecord],
    entity: str
) -> List[ExecutionRecord]:
    """Get all executions by a specific entity"""
    return [e for e in logs if e.executor == entity]


def find_wake_conditions(logs: List[ExecutionRecord]) -> dict:
    """
    Scan logs for wake commands to find current wake conditions.
    Returns: {entity_name: Condition}
    """
    wake_conditions = {}

    for execution in logs:
        # Check if this is a wake command
        from grammar.parser import Text, Condition
        if execution.command.content and \
           isinstance(execution.command.content[0], Text) and \
           "wake" in execution.command.content[0].content:

            # Find Condition node in command tree
            for node in execution.command.content:
                if isinstance(node, Condition):
                    wake_conditions[execution.executor] = node
                    break

    return wake_conditions


def count_spawns(logs: List[ExecutionRecord]) -> int:
    """Count how many entities were spawned"""
    count = 0
    from grammar.parser import Text, Entity

    for execution in logs:
        if execution.command.content and \
           isinstance(execution.command.content[0], Text) and \
           "spawn" in execution.command.content[0].content:
            # Count Entity nodes in command
            entities = [n for n in execution.command.content if isinstance(n, Entity)]
            count += len(entities)
    return count
