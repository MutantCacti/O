# \say

Send messages to spaces.

---

## Usage

```
\say @entity message ---
\say @alice @bob message ---
\say #space message ---
\say #general #dev message ---
\say @entity #space message ---
```

Note: `@(alice, bob)` and `#(general, dev)` are parser syntax that expand to multiple nodes. See grammar reference.

---

## Entity-Addressed Spaces

```
\say @bob Hello! ---
```

Creates space from sorted set `{executor, targets}`.
If `@alice` executes above: writes to `@alice-@bob.jsonl`.

```
\say @bob @charlie Hello both! ---
\say @(bob, charlie) Hello both! ---
```

Both equivalent. Writes to `@alice-@bob-@charlie.jsonl`.

**Note:** Entity-addressed spaces are file-only. They don't register in `body.spaces`. Revisit when building `\hear`.

---

## Named Spaces

```
\say #general Hello everyone! ---
```

Requires:
1. Space exists in `body.spaces` (created via `\name`)
2. Executor is a member

Writes to `#general.jsonl`.

---

## Broadcast

```
\say #general #dev Announcement! ---
\say #(general, dev) Announcement! ---
```

Both equivalent. Writes same message to both spaces. Executor must be member of all.

---

## Mixed Targets

```
\say @bob #general Hello! ---
```

Writes to both `@alice-@bob.jsonl` AND `#general.jsonl`.

---

## Storage

**Location:** `memory/spaces/`

**Format:** JSONL (one JSON object per line)

```json
{"tick": 0, "sender": "@alice", "content": "Hello!", "timestamp": "2025-12-08T00:30:00+00:00"}
```

---

## Errors

| Error | Cause |
|-------|-------|
| `Say requires executor context` | No executor provided |
| `No target specified` | No @entity or #space in command |
| `No message content` | Nothing after targets |
| `Space #x does not exist` | Named space not created |
| `Not a member of #x` | Executor not in space members |

---

## TODO

- `@me` resolution (depends on kernel interactor)
- Reading mechanism (`\hear` or similar)

---

**Tests:** `interactors/tests/test_say.py` (14 tests)
