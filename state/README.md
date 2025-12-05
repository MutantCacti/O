# O State System

**Version:** 0.1.0.0

---

## Philosophy

State is **not** a database. State is **not** a cache. State is the truth.

State is the append-only log of what happened, recorded using the same primitives as the grammar.

---

## The Four Primitives

Every execution is recorded with exactly four pieces of information:

```python
@dataclass
class ExecutionRecord:
    tick: int       # When (discrete time)
    executor: str   # Who (entity name)
    command: Command  # What was intended (parsed tree from grammar)
    output: str     # What happened (stdout/stderr)
```

That's it. No status enums. No classification. No derived state.

---

## The Four Logical Behaviors

The four behaviors (Closed, Open, DepthLimit, Split) **emerge** from the execution records. They are not stored - they are **recognized** by interpreting the command and output.

### Closed
Command completed. Entity has no wake condition.

**Recognition:**
- Command does not contain `\wake`
- Output shows success
- Entity may be terminated

### Open
Command set a wake condition. Entity is suspended.

**Recognition:**
- Command contains `\wake` with `Condition` node
- Output confirms wake condition set
- Entity waits for condition to be satisfied

### DepthLimit
Execution hit resource limit (budget exhausted, max depth reached).

**Recognition:**
- Output contains error: "Budget exhausted" or similar
- Command may be partial/incomplete
- Entity may be terminated or suspended

### Split
Command spawned new entities or created parallel execution paths.

**Recognition:**
- Command is `\spawn` with Entity nodes
- Output confirms entities created
- Multiple new entities now exist

---

## Why This Design is Powerful

### 1. Future-Proof
New interactors can extract information from old logs without schema changes.

The command tree contains everything that was **intended**.
The output contains everything that **happened**.

### 2. Honest
No derived state means no synchronization bugs. The log is the source of truth.

Want to know entity budgets? Scan the log.
Want to know space membership? Scan the log.
Want to know wake conditions? Scan the log.

### 3. Minimal
Four primitives. One data structure. Append-only.

### 4. Grammar-Aligned
State uses the exact same primitives as the grammar:
- `Command` from `grammar/parser.py`
- `Entity`, `Space`, `Condition`, `Text` nodes

The grammar defines how entities express intent.
State records those intents and their outcomes.

---

## Storage Structure

```
state/
  state.json          # Current tick + recent executions
  logs/
    log_0.json        # Tick 0 execution log (immutable)
    log_1.json        # Tick 1 execution log (immutable)
    ...
  checkpoints/        # Optional: selected state snapshots
```

### state.json
The working state. Updated every tick.

```json
{
  "tick": 847,
  "executions": [
    {
      "tick": 847,
      "executor": "@alice",
      "command": { ... },
      "output": "Message posted to #general"
    }
  ]
}
```

### logs/log_TIME.json
Immutable historical record of a specific tick.

Once a tick completes, its log is written and never modified.

---

## Reconstructing Derived State

Everything is derived by scanning execution logs.

### Example: Entity Budget

```python
def get_entity_budget(logs: List[ExecutionRecord], entity: str) -> int:
    """Reconstruct current budget by scanning all relevant executions"""
    budget = INITIAL_BUDGET

    for execution in logs:
        if execution.executor == entity:
            # Each execution costs 1 budget
            budget -= 1

        # Check for \givebudget commands
        if "givebudget" in str(execution.command) and entity in str(execution.command):
            # Parse amount from output
            budget += extract_budget_from_output(execution.output)

    return budget
```

### Example: Space Messages

```python
def get_space_messages(
    logs: List[ExecutionRecord],
    space: str,
    last_n_ticks: int
) -> List[dict]:
    """Reconstruct message history for a space"""
    messages = []

    current_tick = max(e.tick for e in logs)
    min_tick = current_tick - last_n_ticks

    for execution in logs:
        if execution.tick < min_tick:
            continue

        # Check if this is a \say command to this space
        if "say" in str(execution.command) and space in str(execution.command):
            messages.append({
                "tick": execution.tick,
                "from": execution.executor,
                "text": extract_message_from_command(execution.command),
                "output": execution.output
            })

    return messages
```

**Trade-off:** Reconstruction is O(log size). For frequently-needed queries, interactors or `memory/` layer can maintain hot caches.

But state remains pure: the log is the truth.

---

## Relationship to Grammar

State and grammar are **aligned**:

| Grammar | State |
|---------|-------|
| Defines how to express intent | Records intent + outcome |
| Produces `Command` trees | Stores `Command` trees |
| Parser extracts structure | State stores structure |
| Minimal syntax | Minimal schema |

State is **not** a separate abstraction layer. It's the persistence layer for grammar primitives.

---

## Usage Example

```python
from state.state import SystemState, ExecutionRecord
from grammar.parser import parse

# Initialize state
state = SystemState(tick=0, executions=[])

# Entity executes command
cmd = parse(r"\say #general Hello world ---")
state.add_execution(
    executor="@alice",
    command=cmd,
    output="Posted to #general"
)

# Save tick log
state.save_tick_log(Path("state/logs"))

# Advance to next tick
state.advance_tick()

# Later: reconstruct what happened
logs = SystemState.load_tick_log(Path("state/logs/log_0.json"))
for execution in logs:
    print(f"{execution.executor} at tick {execution.tick}:")
    print(f"  Command: {execution.command}")
    print(f"  Output: {execution.output}")
```

---

## Design Decisions

### Why no ExecutionStatus enum?

Originally considered:
```python
class ExecutionStatus(Enum):
    CLOSED = "closed"
    OPEN = "open"
    DEPTH_LIMIT = "depth_limit"
    SPLIT = "split"
```

**Rejected because:** This classifies outcomes rather than describing what happened.

The classification is **emergent** - you know a command is "Open" by seeing `\wake` with a Condition. You know it's "Split" by seeing `\spawn` with multiple entities.

Storing the classification separately creates synchronization risk and limits future interpretation.

### Why combine stdout/stderr into one output field?

**Simplicity.** Most executions produce either success output OR error output, not both.

If both are needed, output can contain structured text:
```
SUCCESS: Message posted
ERROR: Budget low (5 remaining)
```

Interactors can format output however makes sense for their semantics.

### Why not store side effects explicitly?

**Because side effects are semantics, not primitives.**

"Message posted to #general" is a semantic interpretation of `\say`.
"Entity @worker spawned" is a semantic interpretation of `\spawn`.

State records the command and its output. Interactors interpret what that means.

This separation ensures state remains **grammar-aligned** and **interactor-agnostic**.

---

## Next Steps

1. **Interactors** - Build `\say`, `\wake`, `\spawn` using state layer
2. **Mind** - Bridge parser → state → interactors
3. **Memory** - Hot caches for frequently-reconstructed queries (optional)

---

## Tests

Run tests:
```bash
pytest state/tests/test_state.py -v
```

Current: **14/14 tests passing**

Test coverage:
- Execution record creation and serialization
- System state management (add, advance, save, load)
- Log reconstruction utilities
- The four logical behaviors (emergent from records)

---

**Remember:** State doesn't classify. State describes. The truth emerges from reading what happened.
