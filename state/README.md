# O State System

State is the append-only log of command executions.

---

## The Four Primitives

```python
@dataclass
class ExecutionRecord:
    tick: int
    executor: str
    command: str      # Command string (parse when needed)
    output: str
```

---

## The Four Behaviors

Closed, Open, DepthLimit, Split **emerge** from reading records.

Recognition is interpretation, not storage.

---

## Storage

```
state/
  state.json       # Current tick + executions
  logs/
    log_847.json   # Immutable tick logs
```

Format:
```json
{
  "tick": 847,
  "executions": [
    {
      "executor": "@alice",
      "command": "\\say #general Hello ---",
      "output": "Posted"
    }
  ]
}
```

Tick stored once per log, not per execution.

---

## API

```python
state.add_execution(executor, command, output)
state.save_tick_log(log_dir)
state.advance_tick()
```

---

**Tests:** 12/12 passing

**Remember:** State doesn't classify. State describes.
