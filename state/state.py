"""
O State System

State is the append-only log of command executions.
Three primitives per execution: executor, command, output.
Tick stored once per log.
"""

from dataclasses import dataclass
from typing import List
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
    - executor: Who (entity name)
    - command: What was intended (string)
    - output: What happened
    """
    executor: str
    command: str
    output: str

    def get_command(self) -> Command:
        """Parse command string to Command tree"""
        return parse(self.command)

    def to_dict(self) -> dict:
        """Serialize to JSON"""
        return {
            "executor": self.executor,
            "command": self.command,
            "output": self.output
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'ExecutionRecord':
        """Deserialize from JSON"""
        return cls(
            executor=data["executor"],
            command=data["command"],
            output=data["output"]
        )


@dataclass
class SystemState:
    """
    Current state of the O system.

    State is the tick number + execution log for this tick.
    """
    tick: int
    executions: List[ExecutionRecord]

    def add_execution(self, executor: str, command: str, output: str):
        """Record a new command execution"""
        record = ExecutionRecord(
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
            "version": "0.1.0",  # For future state format migrations
            "tick": self.tick,
            "executions": [e.to_dict() for e in self.executions]
        }

        with open(log_path, 'w') as f:
            json.dump(data, f, indent=2)

    def save_state(self, state_path: Path):
        """Save current state to state.json"""
        data = {
            "version": "0.1.0",  # For future state format migrations
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
    def load_tick_log(cls, log_path: Path) -> tuple[int, List[ExecutionRecord]]:
        """Load a specific tick log, returns (tick, executions)"""
        with open(log_path) as f:
            data = json.load(f)

        executions = [
            ExecutionRecord.from_dict(e)
            for e in data["executions"]
        ]

        return data["tick"], executions

    def advance_tick(self):
        """Move to next tick, clear execution buffer"""
        self.tick += 1
        self.executions = []
