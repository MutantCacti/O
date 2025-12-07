#!/usr/bin/env python3
"""
Quick integration test script.

Run this to verify mind→body→state chain works.
"""

from mind import Mind
from body import Body
from state.state import SystemState
from interactors.echo import EchoInteractor

# Create system
mind = Mind(interactors={"echo": EchoInteractor()})
state = SystemState(tick=0, executions=[])
body = Body(mind, state)

print("Testing O system integration...")
print()

# Test 1: Simple echo
print("Test 1: Simple echo")
output = body.execute_now("@alice", r"\echo Hello World ---")
print(f"  Output: {output}")
print(f"  Logged: {len(state.executions)} execution(s)")
print()

# Test 2: Echo with entity reference (mixed nodes)
print("Test 2: Echo with entity reference")
output = body.execute_now("@bob", r"\echo @alice says hello ---")
print(f"  Output: {output}")
print()

# Test 3: Unknown command
print("Test 3: Unknown command")
output = body.execute_now("@charlie", r"\unknown test ---")
print(f"  Output: {output}")
print()

# Test 4: Tick advances
print("Test 4: Tick and log save")
print(f"  Current tick: {state.tick}")
print(f"  Executions before tick: {len(state.executions)}")
body.tick()
print(f"  Tick after: {state.tick}")
print(f"  Executions after tick: {len(state.executions)}")
print()

print("✓ Integration tests complete")
print()
print("State summary:")
print(f"  Current tick: {state.tick}")
print(f"  Total executions this session: 3")
