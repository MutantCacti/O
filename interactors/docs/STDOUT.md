# \stdout Interactor Reference

**Version:** 0.1.0.0
**Status:** Implemented
**Purpose:** Memory persistence layer - write and read execution output logs
**Disclaimer:** State examples like budget and scale are rhetorical and should not be assumed to hold for the current version of O.

---

## Overview

`\stdout` enables entities to persist memory across time by writing to and reading from their execution output streams. This is the foundation for state reconstruction in O's stateless architecture.

**Key concept:** Interactors are stateless. To reconstruct what they did previously, they query stdout.

---

## Syntax

### Write
```bash
\stdout write: Your log entry here ---
\stdout Just write directly (implicit write) ---
```

### Read
```bash
\stdout read: last 10 ---     # Last 10 entries (default)
\stdout read: last 5 ---      # Last 5 entries
\stdout read: ---             # Defaults to last 10
```

---

## How It Works

### Storage Format
- **Location:** `memory/stdout/@entity.jsonl`
- **Format:** JSON Lines (one JSON object per line)
- **Entry structure:**
```json
{
  "tick": 42,
  "entity": "@alice",
  "content": "Your message",
  "timestamp": "2025-12-06T17:33:23.651621"
}
```

### Why JSONL?
- **Append-only:** Fast writes, no file locking
- **Streamable:** Can read line-by-line, no need to load entire file
- **Human-readable:** Debug with `cat`, `grep`, `jq`
- **Simple:** No database required

### Command Parsing

The parser creates a Text node containing the entire command text:
```
\stdout write: Hello ---  →  Text("stdout write: Hello ")
```

The stdout interactor manually parses this text:
1. Split on `:` to separate operation from content
2. Check if "write", "read", or "query" appears in operation part
3. Extract content/params after the `:`

**This is intentional.** Operations like "write" and "read" are not grammar elements (like `@entity` or `#space`). They're text that the interactor interprets.

---

## Usage Patterns

### Basic Logging
```bash
\stdout write: Initialized with config A ---
\stdout write: Processed 42 messages ---
\stdout write: Entering sleep mode ---
```

### Implicit Write
```bash
\stdout Starting task X ---
\stdout Completed task X ---
```
(No "write:" keyword needed - defaults to write operation)

### Reading History
```bash
\stdout read: last 5 ---
```
Output:
```
Last 5 stdout entries for @alice:
  [tick 38] Initialized with config A
  [tick 39] Processed 42 messages
  [tick 40] Entering sleep mode
  [tick 41] Starting task X
  [tick 42] Completed task X
```

### State Reconstruction Pattern
```bash
# On wake, entity reconstructs what it was doing:
\stdout read: last 20 ---

# Parse output to find:
# - What task was in progress?
# - What entities were involved?
# - What was the next step?
```

---

## Architecture Context

### Why Stdout Exists

O's architecture has four components:
1. **Mind** - Execution engine (stateless)
2. **Body** - Environment/physics layer
3. **State** - Tick counter + execution log
4. **Interactors** - System calls (stateless)

**Problem:** Interactors are stateless but need to query previous outputs. Sequential scanning doesn't scale.

**Solution:** \stdout provides random access to execution history through:
- KV lookups (last execution, budget state)
- Recent cache (hot last 100 entries)
- Temporal scans (filtered by tick range)

### Design Principles

**Storage is cheap** (1TB SSD available):
- Store ALL raw data
- Optimize for queryability, not space
- Human-readable formats for debugging

**8 minutes per tick**:
- Time scale matches human interaction
- ~300MB/day data generation at 800 entities
- Week-long tests = 2-5GB total

**Cost-limited budgets**:
- Not token-limited
- Entities get full context windows
- Budget based on API cost ($100/entity)

---

## Implementation Details

### Text Node Parsing

Unlike `\name` which uses grammar nodes (`Space`, `Entity`), `\stdout` parses Text content:

**name.py pattern:**
```python
for node in cmd.content:
    if isinstance(node, Space):
        space_id = f"#{node.name}"  # Grammar extracted it
```

**stdout.py pattern:**
```python
for node in cmd.content:
    if isinstance(node, Text):
        text = node.text.strip()
        if ":" in text:
            parts = text.split(":", 1)
            op_part = parts[0].strip().lower()
            if "write" in op_part:
                operation = "write"
                content_text = parts[1].strip()
```

**Why the difference?**
- Grammar defines structural elements (`@`, `#`, `?()`, `$()`)
- Operations like "write"/"read" are semantic, not structural
- Parser doesn't know what commands do, only what they look like
- Interactors interpret meaning from structure

### Error Handling

**Requires executor context:**
```bash
\stdout write: Test ---  # Without executor
→ ERROR: Stdout requires executor context
```

**Empty content:**
```bash
\stdout write: ---
→ ERROR: No content to write. Usage: \stdout write: message ---
```

**Invalid read params:**
```bash
\stdout read: yesterday ---
→ ERROR: Unknown read pattern 'yesterday'. Try: last 10
```

---

## Implementation Status

### Query Operations (Partially Implemented)

**Current:** Simple substring matching
```bash
\stdout query: error ---           # Case-insensitive substring match
\stdout query: @bob ---            # Find entity mentions
```

**Future:** Condition-based queries (pending parser/mind finalization)
```bash
\stdout query: ?(tick > 42 and content contains "error") ---
\stdout query: ?(after tick 42) ---
\stdout query: ?(between tick 10 and 20) ---
```

**Note:** The current query implementation uses simple pattern matching. Once condition
parsing and evaluation are finalized in the parser/mind, query will be updated to support
full condition expressions with boolean logic, tick comparisons, and content filters.

### Index-Based Queries (Future)
```bash
\stdout budget: ---              # O(1) KV lookup
\stdout last-execution: ---      # O(1) cache hit
\stdout recent: ---              # O(1) recent cache
```

### Multi-Strategy Backend
- **Exact lookups** → Dict/KV store
- **Recent access** → In-memory cache (last 100)
- **Temporal scans** → JSONL sequential read with filters
- **Graph queries** → (Future: relationships between entities)

---

## Testing

**Location:** `interactors/tests/test_stdout.py`

**Coverage:**
- ✓ Basic write functionality
- ✓ Multiple writes (append behavior)
- ✓ Read when empty
- ✓ Read last N entries
- ✓ Read default (last 10)
- ✓ Implicit write (no "write:" keyword)
- ✓ Executor requirement validation
- ✓ Empty content validation

**Run tests:**
```bash
venv/bin/python3 -m pytest interactors/tests/test_stdout.py -v
```

---

## Common Questions

### Q: Why not use a database?
**A:** Simplicity and debuggability. JSONL files can be inspected with standard Unix tools. No schema migrations. No query language to learn. Storage is cheap.

### Q: Why is tick included in entries?
**A:** Temporal ordering. Entities need to reconstruct what happened when. Tick provides absolute time reference across the system.

### Q: Can entities read each other's stdout?
**A:** Currently, `\stdout read:` only reads the executor's own stdout. Cross-entity queries would require different permissions/interactor.

### Q: How do you handle stdout growing forever?
**A:** For now, we don't. Storage is cheap (1TB). Future: archival/compression after N ticks, or query-time filtering.

### Q: Why manually parse text instead of adding grammar?
**A:** Grammar minimalism. "write" and "read" are semantics specific to stdout. They shouldn't pollute the parser. Other interactors might have different operations. Push complexity to interactors, not grammar.

---

## Related Documentation

- **Grammar reference:** `grammar/docs/REFERENCE.md`
- **Parser implementation:** `grammar/parser.py`
- **Interactor base class:** `interactors/base.py`
- **Name interactor (reference pattern):** `interactors/name.py`
- **Data footprint analysis:** `spec/DATA_FOOTPRINT_ANALYSIS.md`

---

**Remember:** Stdout is how interactors remember. Without it, every execution starts from zero knowledge.
