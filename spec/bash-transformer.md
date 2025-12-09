# CLI Transformer - Interactive Interface to O

## Goal

Allow humans and scripts to act as entities within O.

## Two Modes

### 1. One-shot (for Claude/scripts)
```bash
o-send @alice '\echo Hello ---'
```

### 2. Interactive REPL (for humans)
```bash
o-shell @alice
# Polls output FIFO, displays messages as they arrive
# Type commands, hit enter to send
# Like a chat client
```

## Prerequisites

Before CLI can work, entity must exist. This requires `\spawn` interactor.

```
\spawn @alice ---
```

Creates entity, sets up FIFOs via Body's transformer.

## Implementation Order

1. `\spawn` interactor (creates entity + FIFOs)
2. `o-shell` (interactive REPL for humans)
3. `o-send` (one-shot for scripts/Claude)

## Open Questions

1. **Name**: `o-shell`? `o-cli`? `osh`?
2. **FIFO location**: Default to `./fifos/` or configurable?
3. **Output format**: Raw JSON or pretty-printed?
