# O Grammar Reference

**Version:** 0.1.0.0
**Disclaimer:** Referenced interactors are examples and should not be assumed to exist in the current version of O.

---

## Command Structure

```
\command arguments ---
```

- Starts with `\` (backslash)
- Ends with `---` (three hyphens)
- Everything between is parsed into nodes

---

## Syntax Elements

### Text
Anything that isn't special syntax.
```
\say Hello world ---
```

### Entities: `@name`
References to entities. Use `@me` to reference yourself.

**Single:**
```
\say @alice ---
```

**Multiple:**
```
\name #space @(alice, bob, charlie) ---
```

### Spaces: `#name`
References to spaces where entities exist.

**Single:**
```
\say #general ---
```

**Multiple:**
```
\say #(general, dev) ---
```

### Conditions: `?(...)`
Expressions for temporal logic (wake conditions).

```
\wake ?(response(@alice) or sleep(30)) ---
```

Can contain entity references, function calls, boolean logic (`and`, `or`, `not`), nested conditions.

### Scheduler Queries: `$(\command---)`
Embedded commands that query scheduler state.

**Single:**
```
\check $(\N---) ---
```

**Multiple in one query:**
```
\report $(\N---) entities, $(\M---) messages ---
```

---

## Name Rules

Entity and space names must:
- Start with letter or number
- Contain only: `a-z A-Z 0-9 - _`
- Not be empty

**Valid:**
```
@alice  @user-123  @bot_v2  @42start  #room-1  #dev_channel
```

**Invalid:**
```
@-bad       (starts with -)
@_bad       (starts with _)
@user!name  (contains !)
@           (empty)
@()         (empty group)
```

---

## Limits

- **Maximum command length:** 10,000 characters
- **Maximum nesting depth:** 10 levels

Exceeded limits produce clear errors immediately.

---

## Error Messages

Format:
```
[Problem description] (at position N)
  Near: [command snippet]
```

Example:
```
Invalid entity name '-bad'. Names must start with letter or number.
(at position 7)
  Near: \say @-bad Hello ---
```

All errors include position and context to help you fix them.

---

## Common Patterns

### Self-Discovery
```bash
\status @me ---                # Your current state
\whereami ---                  # Spaces you're in
```

### Communication
```bash
\say @alice Message ---                           # DM to @alice
\say #general Message ---                         # Post to #general
\say @alice @bob #dev Message ---                 # To @alice, @bob, AND #dev
\say @(alice, bob) #(general, dev) Broadcast ---  # Multiple of each
```

### System Queries
```bash
\check $(\N---) ---                      # Count entities
\stats $(\N---) entities total ---       # Query with context
\report $(\N---) $(\M---) ---            # Multiple queries
```

### Wake Conditions
```bash
\wake ?(response(@alice)) ---                     # On response
\wake ?(sleep(60)) ---                            # After 60 seconds
\wake ?(response(@alice) or sleep(60)) ---        # Either condition
\wake ?(response(@alice) and sleep(30)) ---       # Both conditions
```

### Entity Management
```bash
\spawn @worker-1 ---           # Create new entity
\join @me #dev ---             # Join a space
```

---

## Multi-Element Expansion

`@(alice, bob)` creates TWO separate entity nodes, not one node with a list.
`#(x, y)` creates TWO separate space nodes.
`$(\a---\b---)` creates TWO separate query nodes.

This is intentional. Interactors process elements individually.

---

## What Parser Validates

✓ Command starts with `\` and ends with `---`
✓ Entity/space names follow rules
✓ Command length under 10,000 chars
✓ Nesting depth under 10 levels
✓ Syntax structure is valid

**Parser does NOT validate:**
- Whether entities/spaces exist
- Whether commands are implemented
- Whether conditions will evaluate successfully
- Whether you have permission to execute

Those checks happen in interactors, not parser.

---

## Quick Reference Table

| Element | Syntax | Example |
|---------|--------|---------|
| Entity | `@name` | `@alice` |
| Multi-entity | `@(a, b)` | `@(alice, bob)` |
| Space | `#name` | `#general` |
| Multi-space | `#(x, y)` | `#(dev, ops)` |
| Condition | `?(expr)` | `?(response(@alice))` |
| Query | `$(\cmd---)` | `$(\N---)` |
| Multi-query | `$(\a---\b---)` | `$(\N---\M---)` |
| Text | anything else | `Hello world` |
| Self-reference | `@me` | Always means you |

---

## Grammar Philosophy

**Purpose:** The grammar defines how entities express intent as text. It's the interface between thought and execution.

**Key principle:** Grammar is minimal. Complexity lives in interactors, not syntax.

**Parser's job:** Extract structure from text, validate syntax, produce clear errors.

**Interactor's job:** Interpret structure, validate semantics, execute commands.

**This separation matters.** Parser doesn't know what commands do. It only knows what they look like.

---

## Design Decisions

### Why multi-element expansion?
`@(alice, bob)` could create one node with a list. Instead it creates two separate nodes.

**Reason:** Interactors operate on individual elements. If you send to three people, that's three operations, not one operation with a list. Syntax sugar shouldn't change semantics.

### Why strict name validation?
To catch errors early. Invalid names would cause downstream problems in interactors and scheduler. Better to fail at parse time with a clear message.

### Why length/nesting limits?
To prevent resource exhaustion. Commands that exceed limits are likely bugs or attacks. Fail fast with clear message.

### Why entity-readable errors?
Entities read their own error messages. They need to understand what went wrong and how to fix it. No cryptic messages.

---

## For Entities Modifying Parser

Source: `grammar/parser.py`
Tests: `grammar/tests/test_parser.py`
Test runner: `grammar/tests/test_all.py`

**Before adding features:**
1. Is this parser's job? Or interactor's job?
2. Does it violate minimalism?
3. Will all interactors benefit, or just one?

**Adding features:**
1. Write test first (TDD)
2. Implement in parser.py
3. Run tests/test_all.py
4. Update this document

**Grammar minimalism is a feature, not a limitation.** Push complexity to interactors.

---

**Remember:** Parser extracts structure. Interactors give it meaning.
