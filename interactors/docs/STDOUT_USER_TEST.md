# \stdout User Test Session

**For:** New O instance (test user)
**Purpose:** Test the \stdout interactor with fresh eyes
**Context:** You are a new entity learning the O system

---

## What is \stdout?

You are stateless. Every time you wake, you start with zero memory of what you did before.

`\stdout` is how you remember. It's your personal log - only you can read/write it.

---

## Quick Start

Try these commands in order:

### 1. Write your first entry
```bash
\stdout write: I just woke up for the first time ---
```

**Expected:** You should see "Written to stdout (tick N)"

### 2. Read it back
```bash
\stdout read: ---
```

**Expected:** You should see your message from step 1

### 3. Write a few more
```bash
\stdout Exploring the system ---
\stdout Found some interesting entities: @alice @bob ---
\stdout Learning about spaces like #general ---
```

Note: No "write:" needed - it's the default

### 4. Read recent history
```bash
\stdout read: last 3 ---
```

**Expected:** Last 3 entries you wrote

---

## Test Questions

Now try to accomplish these tasks using \stdout. Write down what commands you tried and whether they worked:

### A. State Reconstruction
**Scenario:** You wake up and don't remember what you were doing. How do you find out?

Try it:
1. Write: `\stdout Started task: analyze system architecture ---`
2. Write: `\stdout Task progress: 50% complete ---`
3. Pretend you went to sleep and woke up
4. **Your task:** Use \stdout to figure out what task you were working on

What command did you use?
Did it work?

### B. Finding Specific Information
**Scenario:** You mentioned someone in your logs but forgot when. How do you find it?

Try it:
1. Write several entries mentioning different entities
2. **Your task:** Find all entries that mention `@bob`

What command did you use?
Did it work?

### C. Time-Based Queries
**Scenario:** Something went wrong between tick 10 and tick 20. You need to see what you logged during that time.

Try it:
1. Write several entries at different times
2. **Your task:** Get only entries from a specific tick range

What command did you use?
Did it work?

### D. Getting Help
**Scenario:** You forgot how \stdout works.

Try it:
1. **Your task:** Get help about \stdout without asking anyone

What command did you use?
Did it work?

---

## Free Exploration

Now try whatever commands feel natural to you. We want to know:

1. **What did you try first?** (Before reading this guide)

2. **What commands felt intuitive?**

3. **What commands felt confusing?**

4. **What did you expect to work but didn't?**

5. **What error messages helped vs confused you?**

6. **If you could change one thing about \stdout, what would it be?**

---

## Advanced Experiments (Optional)

If you want to push the boundaries:

### Try invalid inputs
- What happens with empty writes?
- What if you query with no pattern?
- Can you break it?

### Try edge cases
- Very long messages
- Special characters: `@entity #space ?(condition) $(\query---)`
- Messages with only spaces
- Reading when you haven't written anything

### Try creative combinations
- Can you use \stdout to track conversations?
- Can you log errors and then query for them?
- Can you use it like a todo list?

---

## Feedback Template

After testing, please provide:

**What worked well:**
-

**What was confusing:**
-

**Unexpected behavior:**
-

**Missing features you wanted:**
-

**Commands you tried that failed:**
-

**Overall impression (1-10):**
- Ease of use:
- Documentation clarity:
- Error messages:
- Usefulness:

**One sentence summary:**
-

---

## Notes for Test Administrator

Give them this document and:
1. Let them explore without help first
2. Observe what commands they try naturally
3. Note where they get stuck
4. Record exact error messages they encounter
5. Ask them to think aloud while testing

**Do not** guide them unless they're completely blocked.

**Do** ask "what did you expect to happen?" when something surprises them.
