# Changelog

## [0.1.0.0-alpha.1] - 2025-12-07

**Pre-release**: Core runtime complete. Full release (v1.0.0) will include all boot interactors and working meta-control.

### Added
- Complete O grammar parser with command, entity, space, condition, and text nodes
- Mind execution engine with interactor routing
- Body tick loop with transformer polling
- State persistence (per-tick logs, per-entity stdout streams)
- DeepSeek transformer (OpenAI-compatible LLM integration)
- Core interactors: `\stdout`, `\echo`, `\name`, `\wake`
- Transformer device pattern (Body polls I/O devices for commands)
- 257 passing tests (unit + integration, fully mocked)
- Live API test framework with test/production key separation
- First autonomous execution: @alice (DeepSeek) at tick 0

### Architecture
- Transformers are external I/O devices (LLMs, humans)
- Body polls transformers each tick
- Mind routes parsed commands to interactors
- Interactors mutate state directly (Unix syscall pattern)
- State persists via JSONL (stdout) and JSON (logs)

### Testing
- Full test coverage with mocked API calls
- Safe API key management (DEEPSEEK_TEST_API_KEY)
- Live tests require explicit opt-in

### Documentation
- README with architecture overview and examples
- .env.example for configuration
- pyproject.toml for packaging
- LICENSE (MIT)
- State format versioning for future migrations

### Known Limitations
- Synchronous tick loop (async/Litestar planned)
- Wake condition evaluation not yet implemented
- No \say interactor yet (entity-to-entity communication)
- File-based persistence only (distributed state planned)
