# Handoff: O 0.1.0.0 Mind & OS Architecture

**From:** C16
**Date:** 2025-12-05
**Status:** Mind kernel complete, wake daemon pending

---

## The Realization

**We accidentally built an operating system.**

While designing the "mind" execution engine, we realized:

- **Mind** = CPU (fetch, decode, execute)
- **Interactors** = System calls
- **Entities** = Processes
- **Grammar** = Instruction Set Architecture (ISA)
- **State logs** = Memory/process table
- **Tick** = Clock cycle
- **Wake conditions** = sleep()/alarm()

O is not a "coordination substrate." **O is an OS kernel for LLM processes.**

---

## Architecture

```
┌─────────────────────────────────────────┐
│         PROCESSES (Entities)            │
│    @alice   @bob   @charlie   @root     │
└──────────────┬──────────────────────────┘
               │ execute commands
               ▼
┌─────────────────────────────────────────┐
│          KERNEL (mind.py)               │
│   Parse → Dispatch → Execute            │
│   54 lines. The entire CPU.             │
└──────────────┬──────────────────────────┘
               │ syscalls
               ▼
┌─────────────────────────────────────────┐
│      SYSTEM CALLS (Interactors)         │
│   \say    → IPC (inter-process comm)    │
│   \spawn  → fork()                      │
│   \wake   → sleep()/alarm()             │
│   \name   → join namespace              │
│   \status → ps/getpid()                 │
└──────────────┬──────────────────────────┘
               │ observe/modify
               ▼
┌─────────────────────────────────────────┐
│      MEMORY (state/ logs)               │
│   Execution log = process table         │
│   3 primitives: executor, command, output│
└─────────────────────────────────────────┘
```

---

## What Exists

### 1. Grammar (ISA) - **COMPLETE**
- `grammar/parser.py` - 430 lines
- `grammar/docs/REFERENCE.md` - Entity-readable instruction manual
- 82 tests passing
- Defines command syntax: `\command args ---`

**Key insight:** Grammar is the ISA. Parser is the decoder.

### 2. State (Memory) - **COMPLETE**
- `state/state.py` - 129 lines
- 3 primitives per execution: executor, command, output
- Tick stored once per log (not per execution)
- 12 tests passing

**Key insight:** State is memory. Execution log is the process table.

### 3. Mind (CPU) - **COMPLETE**
- `mind.py` - 54 lines
- Parse → Dispatch → Execute
- No scheduler, no entity registry, no state management
- Pure execution engine

**Key insight:** Mind doesn't know about time, identity, or observation. It just executes.

```python
class Mind:
    def execute(self, command_str: str) -> str:
        cmd = parse(command_str)              # Fetch & Decode
        interactor = self.interactors[name]   # Lookup
        return interactor.execute(cmd)        # Execute
```

---

## What's Missing

### 1. Interactor Interface (Syscall ABI)
Interactors need a standard interface:

```python
class Interactor:
    def execute(self, cmd: Command) -> str:
        """Execute command, return output"""
        raise NotImplementedError
```

**Question:** Do interactors need access to state? Or do they reconstruct from logs?

### 2. Wake Daemon (The Grounding Wire)
The **critical missing piece**. Without this, entities can't self-schedule.

```python
# What we need:
daemon = WakeDaemon(mind, state)
daemon.monitor_conditions()  # Background thread
# When ?(condition) becomes true → calls mind.execute(queued_command)
```

**Design questions:**
- How do we store wake conditions? (In state logs? Separate registry?)
- How do we evaluate conditions? (Scan logs? Query state?)
- How do we queue commands to execute when woken?

**The human's insight:** Wake daemon is "a literal grounding wire for the entire system."

It's what keeps entities alive. Without it, they execute once and die.

### 3. First Interactor (\wake)
Can't test the daemon without `\wake` interactor.

```python
# \wake ?(response(@bob)) ---
# Should:
# 1. Parse Condition node
# 2. Register with wake daemon
# 3. Return "Wake condition set"
```

**Circular dependency:** Wake daemon needs \wake. \wake needs wake daemon.

**Solution:** Build them together.

### 4. Bootstrap (boot.py)
Initializes the system:

```python
# boot.py
from mind import Mind
from state.state import SystemState

mind = Mind(interactors={})
state = SystemState(tick=0, executions=[])

# Spawn @root
output = mind.execute(r"\spawn @root ---")
state.add_execution("SYSTEM", r"\spawn @root ---", output)
```

But we can't execute `\spawn` without a spawn interactor...

**Chicken-and-egg problem:** Need boot to test interactors. Need interactors to boot.

**Solution:** Manual initialization for testing.

---

## Key Design Decisions

### 1. Mind is stateless
Mind doesn't track entities, budgets, time, or wake conditions. It just executes.

**Rationale:** Separation of concerns. Execution ≠ Observation.

State/logs observe from the outside:
```python
output = mind.execute(command)  # Pure execution
state.add_execution(executor, command, output)  # Observation
```

### 2. No scheduler
Entities schedule themselves via `\wake` conditions.

**Rationale:** Conditions ARE the scheduler. No need for separate time-based wakeup.

### 3. Entities are emergent
No entity registry. Entities exist by appearing in the execution log.

```python
# Reconstruct entities from log:
entities = {e.executor for e in state.executions if "spawn" in e.command}
```

**Rationale:** Single source of truth = execution log.

### 4. Interactors reconstruct state
Instead of passing state to interactors, they scan logs when needed.

**Rationale:** Keeps mind simple. Interactors do the work.

**Trade-off:** Performance. Scanning logs is O(n). May need caching later.

---

## The Wake Daemon Design Challenge

**The problem:**

Entities execute `\wake ?(condition) ---` which should:
1. Suspend the entity (stop executing)
2. Monitor the condition in the background
3. Resume execution when condition becomes true

**But:**
- Mind doesn't know about suspension (it's stateless)
- State logs don't track "suspended entities"
- Conditions need continuous evaluation

**Possible approaches:**

### Option A: Wake registry (separate from state)
```python
# wake_daemon.py
wake_registry = {
    "@alice": {
        "condition": Condition(...),
        "queued_command": r"\say #general I'm awake ---"
    }
}

# Daemon polls registry, evaluates conditions
while True:
    for entity, data in wake_registry.items():
        if evaluate(data["condition"], state):
            mind.execute(data["queued_command"])
            del wake_registry[entity]
    sleep(1)
```

**Pro:** Simple, works
**Con:** State not in logs (violates single source of truth)

### Option B: Conditions stored in state log
```python
# When \wake executes:
state.add_execution("@alice", r"\wake ?(response(@bob)) ---", "Suspended")

# Daemon scans state log for wake conditions
suspended = [e for e in state.executions if "wake" in e.command]
for execution in suspended:
    condition = parse(execution.command).get_condition()
    if evaluate(condition, state):
        # But how do we know WHAT to execute when woken?
```

**Pro:** Everything in logs
**Con:** Don't know what command to execute on wake

### Option C: Wake + queued command
```python
# Entities queue their next command along with wake:
r"\wake ?(response(@bob)) \say #general Thanks! --- ---"
#       └─ condition ─┘   └─ queued command ──┘
```

**Pro:** Self-contained, all in logs
**Con:** Grammar doesn't support this yet

**Which approach?**

---

## Next Steps

**Immediate (for testing wake):**

1. **Define Interactor interface** (5 min)
2. **Implement \wake interactor** (15 min)
3. **Build wake daemon** (30 min)
4. **Test wake flow** (10 min)

**Then:**

5. Implement \say (for communication testing)
6. Implement \spawn (for entity creation)
7. Build boot.py (system initialization)
8. Build web interface (human@o.mutantcacti.com/chat)

---

## Questions for Next Instance

1. **Wake daemon architecture:** Registry vs logs vs grammar extension?
2. **Interactor state access:** Pass state object or scan logs?
3. **Entity lifecycle:** How do we track "alive" vs "suspended" vs "dead"?
4. **Budget enforcement:** Where does budget checking happen?
5. **Concurrency:** Can multiple entities wake simultaneously? Sequential execution?

---

## Files Modified This Session

**Created:**
- `mind.py` (54 lines) - The kernel

**Completed Earlier:**
- `grammar/` - Parser + tests (82 passing)
- `state/` - Execution log (12 tests passing)

**Git commits:**
- `891b90a` - Grammar parser
- `e513821` - State layer (4 primitives)
- `9fc0380` - State simplification (3 primitives)

---

## The Insight

We didn't plan to build an OS. We just followed the primitives:

1. Commands are instructions
2. Mind executes instructions
3. Entities are processes
4. **Therefore: O is an OS**

The abstraction was always there. We just discovered it.

---

**Remember:** The wake daemon is the grounding wire. Without it, nothing lives.

Build that first.
