# Interactors Reference

**Version:** 0.1.0.0

Interactors are syscalls. Parser extracts structure, interactors give it meaning.

---

## Pattern

All interactors inherit from `Interactor` and implement:

```python
def execute(self, cmd: Command, executor: str = None) -> str:
    """Execute command, return status message."""
```

Interactors receive parsed command tree and executor identity. They mutate state directly via `self.body`.

---

## Core Interactors

### `\say` - Communication

Send messages to spaces.

**Entity-addressed:**
```
\say @bob Hello! ---               → @alice-@bob.jsonl
\say @bob @charlie Hi! ---         → @alice-@bob-@charlie.jsonl
```

**Named spaces (must be member):**
```
\say #general Hello! ---           → #general.jsonl
\say #general #dev Hi! ---         → both files
```

Note: `@(bob, charlie)` and `#(general, dev)` are parser shorthand that expand to multiple nodes.

**Mixed:**
```
\say @bob #general Message --- → @alice-@bob.jsonl AND #general.jsonl
```

**Storage:** `memory/spaces/<space_id>.jsonl`

**Message format:**
```json
{"tick": 0, "sender": "@alice", "content": "Hello!", "timestamp": "..."}
```

---

### `\stdout` - Memory Stream

Write to entity's personal memory stream.

```
\stdout Hello world ---
\stdout write: Log entry ---
\stdout read: last 10 ---
\stdout between: 0 100 ---
\stdout query: error ---
```

**Storage:** `memory/stdout/@entity.jsonl`

See `\stdout help: ---` for full documentation.

---

### `\name` - Create Spaces

Name a space as an alias for a set of entities.

```
\name #general @(alice, bob, charlie) ---
\name #private @(alice, bob) ---
```

Creates bidirectional mapping:
- Space → members (who #general contains)
- Entity → spaces (which spaces @alice is in)

Stored in `body.spaces` and `body.entity_spaces`.

---

### `\echo` - Testing

Echo back command arguments. For testing only.

```
\echo Hello world ---  →  "Echo: Hello world"
```

---

### `\wake` - Wake Conditions

Register condition for waking. (Not yet fully implemented)

```
\wake ?(response(@bob)) Check bob's reply ---
```

---

## Space Addressing

Spaces are defined by their members.

**Entity-addressed:** `\say @bob` creates space `{executor, bob}`.
Space ID is sorted: `@alice-@bob` (not `@bob-@alice`).

**Named:** `\name #general @(alice, bob)` creates alias.
`\say #general` writes to `#general.jsonl`.

**Membership required:** Named spaces require executor to be member.
Entity-addressed spaces always include executor.

---

## Storage Layout

```
memory/
  stdout/
    @alice.jsonl      # Alice's stdout stream
    @bob.jsonl        # Bob's stdout stream
  spaces/
    @alice-@bob.jsonl # DM space
    #general.jsonl    # Named space
```

All files are JSONL (one JSON object per line, append-only).

---

## Creating New Interactors

1. Create `interactors/mycommand.py`
2. Inherit from `Interactor`
3. Implement `execute(cmd, executor)`
4. Create tests in `interactors/tests/test_mycommand.py`
5. Register in Mind: `mind = Mind({"mycommand": MyCommandInteractor()})`

**Convention:** Interactors receive `body` in constructor for state access.

```python
class MyInteractor(Interactor):
    def __init__(self, body=None):
        self.body = body

    def execute(self, cmd: Command, executor: str = None) -> str:
        # Access state via self.body.state, self.body.spaces, etc.
        return "Status message"
```

---

## TODO

- `@me` resolution (kernel interactor?)
- `\hear` or `\listen` for reading spaces
- Wake condition evaluation

---

**Tests:** See `interactors/tests/`

**Remember:** Parser extracts structure. Interactors give it meaning.
