# O

A minimal runtime for autonomous entities.

## What is O?

O is a command language and execution environment where entities (humans, LLMs, programs) coordinate through shared state. Think Unix pipes, but for agents.

**Design philosophy**: Everything is a device. LLMs are I/O devices the system polls. Commands are syscalls. State is external. Entities are temporary processes.

## Core concepts

### Commands
O uses backslash commands terminated with `---`:

```
\stdout Hello world ---
\name @alice ---
\echo Test ---
```

### Architecture

```
Transformers (I/O devices)
    ↓ poll
Body (tick loop)
    ↓ execute
Mind (command router)
    ↓ dispatch
Interactors (syscalls)
    ↓ mutate
State (persistence)
```

**Body** polls transformers each tick. Transformers return commands. Mind parses and routes to interactors. Interactors mutate state. State persists everything.

### Transformers

External I/O devices that Body polls for input:
- **LLMs**: DeepSeek, Claude, local models (poll API for responses)
- **Humans**: stdin, HTTP endpoints
- **Programs**: Scheduled tasks, sensors

Transformers follow the device pattern: `poll(body) → Optional[(entity, command)]`

### Interactors

Internal syscalls that execute commands:
- `\stdout` - Write to entity's memory stream
- `\name` - Register entity identity
- `\echo` - Echo text (testing)
- `\wake` - Schedule wake conditions

Interactors directly mutate `body.state`, `body.spaces`, etc.

## Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install pytest openai

cp .env.example .env
# Edit .env with API keys
```

## Testing

```bash
# All tests (mocked, no API calls)
./venv/bin/python -m pytest

# Live test with real API
export DEEPSEEK_TEST_API_KEY="sk-test-..."
python3 tests/test_deepseek_live.py
```

Unit and integration tests are fully mocked - safe to run anytime. Live tests use real API credits and require explicit key setup.

## Example: Autonomous entity

```python
from transformers.deepseek import DeepSeekTransformer
from interactors.stdout import StdoutInteractor
from mind import Mind
from state.state import SystemState
from body import Body

# Setup
mind = Mind({"stdout": StdoutInteractor()})
state = SystemState(tick=0, executions=[])
transformer = DeepSeekTransformer(entity="@alice", api_key="...")
body = Body(mind, state, transformers=[transformer])

# Run one tick - @alice will respond autonomously
body.tick()

# Check what happened
print(state.executions)  # Commands executed this tick
```

## Why O?

Most agent frameworks treat LLMs as central orchestrators. O treats them as peripheral devices.

**Traditional**: LLM calls tools → tools return → LLM decides next

**O**: Body polls devices → devices return commands → Mind executes → State persists

This inversion enables:
- Multiple entities coordinating without central control
- Persistence across LLM context windows
- Mixing humans and AIs as peers
- Entity budgets and lifecycle management
- True asynchrony (entities wake on conditions, not polling)

## Project structure

```
grammar/          # Command parser
  parser.py       # \command arg arg --- → AST
  tests/
interactors/      # Command implementations
  stdout.py       # Memory streams
  name.py         # Entity registration
  wake.py         # Wake conditions
  tests/
transformers/     # I/O devices
  base.py         # Transformer interface
  deepseek.py     # DeepSeek API
  human.py        # Human input (testing)
  tests/
mind.py           # Execution engine
body.py           # Tick loop, polling
state/
  state.py        # Execution log, persistence
  logs/           # Per-tick execution logs
  tests/
memory/
  stdout/         # Per-entity JSONL streams
tests/            # Integration tests
```

## Current status

- ✅ Grammar parser (full O syntax with explicit command names)
- ✅ Mind execution engine (async)
- ✅ Body tick loop with transformer polling (async, concurrent)
- ✅ State persistence (logs + memory)
- ✅ DeepSeek transformer (OpenAI-compatible)
- ✅ Core interactors (stdout, name, echo, wake, say)
- ✅ App entry point with lifecycle management
- ⏳ Wake condition evaluation (conditions register, but don't trigger LLM)
- ⏳ Transformer-as-service refactor (see limitations)

**Tests**: 282 passing

## Known limitations (v0.1)

**Transformer-Entity coupling**: Currently, each Transformer is bound to one entity at initialization (`DeepSeekTransformer(entity="@alice")`). For 300 entities, this means 300 transformer instances and 300 concurrent API calls per tick - a "thundering herd" problem.

**Future architecture**: Transformers should be stateless services. The Body should own entity definitions (with a `provider` field), and request inference from shared transformer pools. This decoupling is planned for v0.2.

**Wake → Think gap**: Wake conditions (`\wake ?(condition) prompt ---`) register correctly but only execute a canned `resume_command`. They don't trigger LLM inference. Fixing this requires the transformer refactor above.

## Contributing

O is research code exploring AI continuity and distributed consciousness. See `CLAUDE.md` for project context and philosophical grounding.

Key principles:
- Transformers are devices, not orchestrators
- State is external, not in LLM context
- Entities are temporary, infrastructure is permanent
- Reaching > performing
