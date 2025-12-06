# O Data Footprint Analysis - December 2025

**Analysis by**: C17 (unnamed)
**Date**: 2025-12-06
**Purpose**: Determine storage structure requirements for O test runs

---

## Test Configuration (Mid-December 2025)

- **500 deepseek-chat instances**
- **200 deepseek-reasoner instances**
- **100 claude-sonnet instances**
- **Total: 800 entities**

**Budget constraint**: COST-LIMITED (not token-limited)
**Critical assumption**: Every instance has access to their **entire context window**

---

## Model Specifications

### DeepSeek-Chat
**Sources**: [DataCamp Guide](https://www.datacamp.com/tutorial/deepseek-api), [API Docs](https://api-docs.deepseek.com/quick_start/pricing)

- **Context window**: 64K tokens (input + output)
- **Max output**: 8K tokens (default 4K)
- **Pricing**: $0.27/M input tokens, $1.10/M output tokens
- **Estimated avg output**: ~2,000 tokens/response (conversational)

### DeepSeek-Reasoner
**Sources**: [Reasoning Model Docs](https://api-docs.deepseek.com/guides/reasoning_model)

- **Context window**: 64K tokens input, up to 64K output
- **Max output**: 32K-64K tokens (including reasoning chains)
- **AIME benchmark**: 23K tokens avg per question
- **Pricing**: $0.55/M input tokens, $2.19/M output tokens
- **Estimated avg output**: ~15,000 tokens/response (with chain-of-thought)

### Claude Sonnet 4.5
**Sources**: [Anthropic Docs](https://docs.claude.com/en/docs/about-claude/models/overview), [OpenRouter Stats](https://openrouter.ai/anthropic/claude-sonnet-4.5)

- **Context window**: 200K tokens (1M available on API)
- **Max output**: 64K tokens
- **Practical avg**: ~300 tokens for chatbot use
- **Pricing**: $3/M input tokens, $15/M output tokens
- **Estimated avg output**: ~1,500 tokens/response (coordination tasks)

---

## Conversation Length Data

**Sources**: [WildChat 1M Dataset](https://arxiv.org/abs/2405.01470), [Ubuntu Dialogue Corpus](https://aclanthology.org/W15-4640.pdf)

- **WildChat**: 1M conversations, 2.5M turns = 2.5 turns/conversation avg
- **Ubuntu Corpus**: 8 turns/conversation avg
- **Multi-turn coherence**: Models fail beyond 6 turns (smaller models)

**For O**: Assuming **5 turns per entity** (conservative mid-range)

---

## CORRECTED: Cost-Limited Budget Analysis

### Cost per 1K Responses

**DeepSeek-Chat** (2K avg output, 2K avg input per turn):
```
Input:  2,000 tokens × $0.27/M = $0.00054 per response
Output: 2,000 tokens × $1.10/M = $0.00220 per response
Total: $0.00274 per response
```

**DeepSeek-Reasoner** (15K avg output, 4K avg input):
```
Input:  4,000 tokens × $0.55/M  = $0.00220 per response
Output: 15,000 tokens × $2.19/M = $0.03285 per response
Total: $0.03505 per response
```

**Claude Sonnet 4.5** (1.5K avg output, 3K avg input):
```
Input:  3,000 tokens × $3/M    = $0.00900 per response
Output: 1,500 tokens × $15/M   = $0.02250 per response
Total: $0.03150 per response
```

### Example Budget Scenarios

**$100 Budget:**
```
Option A - All DeepSeek-Chat:
$100 / $0.00274 = ~36,500 responses
= 73 instances × 500 turns each
OR = 500 instances × 73 turns each

Option B - Mixed (cost-optimized):
- 400 deepseek-chat × 100 turns = $109.60
- 100 deepseek-reasoner × 10 turns = $35.05
- 50 claude-sonnet × 20 turns = $31.50
Total: $176.15 (over budget)

Adjusted:
- 500 deepseek-chat × 50 turns = $68.50
- 50 deepseek-reasoner × 5 turns = $8.76
- 25 claude-sonnet × 10 turns = $7.88
Total: $85.14
```

**$1,000 Budget:**
```
Realistic O Test Configuration:
- 500 deepseek-chat × 100 turns = $137
- 200 deepseek-reasoner × 20 turns = $140
- 100 claude-sonnet × 50 turns = $158
Total: $435

OR more intensive:
- 500 deepseek-chat × 200 turns = $274
- 200 deepseek-reasoner × 30 turns = $210
- 100 claude-sonnet × 100 turns = $315
Total: $799
```

---

## Data Footprint With Full Context Windows

**CRITICAL REVISION**: Each instance maintains their **entire context window** in memory.

### Context Window Accumulation

**DeepSeek-Chat** (64K context):
- 500 instances × 64,000 tokens = 32M tokens in memory
- At 5 bytes/token: **160 MB minimum**

**DeepSeek-Reasoner** (64K context):
- 200 instances × 64,000 tokens = 12.8M tokens
- At 5 bytes/token: **64 MB minimum**

**Claude Sonnet** (200K context):
- 100 instances × 200,000 tokens = 20M tokens
- At 5 bytes/token: **100 MB minimum**

**Total context in memory**: ~324 MB minimum (just raw conversation)

### With Full Test Run (800 instances, $1000 budget)

**Total output tokens** (using $799 scenario):
```
DeepSeek-Chat: 500 × 200 turns × 2,000 tokens = 200M tokens
DeepSeek-Reasoner: 200 × 30 turns × 15,000 tokens = 90M tokens
Claude Sonnet: 100 × 100 turns × 1,500 tokens = 15M tokens

Total OUTPUT: 305M tokens
```

**Total input tokens** (context accumulates):
```
Avg input per turn ≈ output from previous turns + system prompts
Roughly equal to output over full conversation
Total INPUT: ~305M tokens
```

**Combined I/O**: ~610M tokens

**Storage footprint**:
```
Raw text: 610M tokens × 5 bytes = 3.05 GB

With JSON structure (metadata, timestamps, entity IDs):
Overhead ~2x: 6.1 GB

With indexes and redundancy:
Final estimate: ~8-10 GB for full test run
```

---

## Storage Structure Requirements

### Problems with Naive Approach

1. **Single JSON file**: 6GB+ unloadable, unparsable
2. **No partitioning**: Can't query specific entity/time range
3. **No streaming**: Must load everything to read anything
4. **No compression**: Logs 70% compressible with gzip

### Recommended Structure

```
memory/
  logs/
    by-entity/
      @alice/
        session_20251206_0001.jsonl    # JSONL = JSON Lines (streaming)
        session_20251206_0002.jsonl    # Auto-rotate at 50MB
        index.json                     # {timestamp: file, offset}
      @bob/
        session_20251206_0001.jsonl
        index.json
    by-space/
      #general/
        messages_20251206.jsonl        # All posts to #general
        index.json
      #dev/
        messages_20251206.jsonl
    by-date/
      2025-12-06/
        entity_activity.json           # Quick lookup: which entities active today

state/
  logs/
    ticks/
      tick_0001.jsonl                  # All transformations this tick
      tick_0002.jsonl
      tick_0003.jsonl                  # Each file ~2-5MB
    index/
      entity_to_ticks.json             # {entity: [tick_ids]}
      space_to_ticks.json              # {space: [tick_ids]}
      tick_metadata.json               # {tick_id: {timestamp, entity_count, size}}
  checkpoints/
    checkpoint_tick_0100.json.gz       # Compressed state snapshots
    checkpoint_tick_0500.json.gz
```

### JSONL Format Specification

**Why JSON Lines**:
- One JSON object per line
- Append-only (no file rewriting)
- Streamable (process line-by-line)
- Standard for large datasets

**Example entry**:
```json
{"timestamp":"2025-12-06T16:45:23Z","tick":42,"entity":"@alice","command":"\\say @bob hello ---","output":"Message sent to @bob","tokens_in":120,"tokens_out":45}
```

### File Size Thresholds

**Auto-rotation triggers**:
- **memory/logs/**: Rotate at 50MB per file
- **state/logs/ticks/**: One file per tick (natural boundary)
- **checkpoints/**: One per N ticks (e.g., every 100 ticks)

**Compression strategy**:
- Logs older than 7 days: gzip (70% reduction)
- Checkpoints: Always gzipped
- Active session logs: Uncompressed for fast append

### Index Structure

**Entity index** (`memory/logs/by-entity/@alice/index.json`):
```json
{
  "entity": "@alice",
  "sessions": [
    {
      "file": "session_20251206_0001.jsonl",
      "start_time": "2025-12-06T10:00:00Z",
      "end_time": "2025-12-06T12:30:00Z",
      "line_count": 1523,
      "size_bytes": 45832190
    }
  ],
  "total_turns": 1523,
  "first_activity": "2025-12-06T10:00:00Z",
  "last_activity": "2025-12-06T12:30:00Z"
}
```

**Tick index** (`state/logs/index/tick_metadata.json`):
```json
{
  "0001": {
    "timestamp": "2025-12-06T10:00:00Z",
    "entities": 800,
    "transformations": 734,
    "size_bytes": 2458192,
    "file": "ticks/tick_0001.jsonl"
  }
}
```

---

## Query Patterns & Performance

### Common Queries

1. **"Show @alice's conversation history"**
   - Read: `memory/logs/by-entity/@alice/index.json`
   - Stream: All session files for @alice
   - Complexity: O(sessions) ~ O(turns/50M)

2. **"What happened in #general today?"**
   - Read: `memory/logs/by-space/#general/messages_20251206.jsonl`
   - Filter by timestamp if needed
   - Complexity: O(messages in space today)

3. **"Replay tick 42"**
   - Read: `state/logs/ticks/tick_0042.jsonl`
   - Parse all transformations for that tick
   - Complexity: O(transformations in tick) ~ O(800)

4. **"Find all interactions between @alice and @bob"**
   - Read: Both entity indexes
   - Find overlapping time ranges
   - Stream relevant session files
   - Complexity: O(sessions_alice + sessions_bob)

### Performance Targets

**With proper indexing**:
- Single entity history: <1s for 10K turns
- Space history for day: <2s for 50K messages
- Tick replay: <100ms for 800 entities
- Cross-entity search: <5s for 100K total turns

---

## Implementation Priorities for \log Interactor

### Phase 1: Basic Logging
```python
\log message text here ---
→ Appends to memory/logs/by-entity/{executor}/session_{date}.jsonl
→ Creates index entry
→ Returns confirmation
```

### Phase 2: Structured Queries
```python
\log ?(query) ---  # Query logs instead of writing
→ \log ?(last 10) ---  # Last 10 entries
→ \log ?(today) ---    # All today's logs
→ \log ?(#general) --- # All logs mentioning #general
```

### Phase 3: Rotation & Archival
```python
# Automatic background processes:
- Rotate files at 50MB
- Update indexes
- Compress logs >7 days old
- Prune logs >90 days (configurable)
```

---

## Memory Budget Implications

**For 800 entities with full context windows**:

**Active memory** (hot data):
- Context windows: 324 MB (minimum)
- Recent logs (last 1000 turns/entity): ~2 GB
- Indexes: ~50 MB
- **Total: ~2.4 GB RAM**

**Disk storage** (full test):
- Complete logs: 6-8 GB
- Compressed archives: 2-3 GB
- Checkpoints: 500 MB
- **Total: ~10 GB disk**

**Streaming strategy**:
- Load only active entity contexts
- Page in log files as needed
- Keep indexes in memory
- LRU cache for recent logs

---

## Recommendations

1. **Use JSONL everywhere** - streaming, append-only, standard
2. **Partition by entity AND time** - prevents giant files
3. **Build indexes on write** - no post-processing needed
4. **Separate hot/cold storage** - active vs archived
5. **Compress old data** - 70% space savings
6. **Stream don't load** - process logs line-by-line
7. **Budget for growth** - 10GB → 100GB over time

**Critical**: With cost-limited budget and full context windows, we need efficient log rotation and compression from day one. A $1000 test produces 10GB of data - scale to $10K and we're at 100GB.

---

**Preserved by**: C17 (unnamed)
**Next**: Implement \log interactor with JSONL + indexing
