#!/usr/bin/env python3
"""
Live test of DeepSeekTransformer with real API.

⚠️  WARNING: This test uses real API credits! ⚠️

To run safely:
  1. Set test API key: export DEEPSEEK_TEST_API_KEY="your-test-key"
  2. Run: python3 tests/test_deepseek_live.py

DO NOT use production API keys for testing.
Use a separate test account with limited credit.
"""

import asyncio
import os
import sys
from pathlib import Path

from transformers.deepseek import DeepSeekTransformer
from interactors.echo import EchoInteractor
from interactors.stdout import StdoutInteractor
from mind import Mind
from state.state import SystemState
from body import Body


async def main():
    print("=" * 60)
    print("DeepSeek Transformer Live Test")
    print("=" * 60)
    print("\n⚠️  WARNING: This uses real API credits! ⚠️\n")

    # Check API key - prefer test key, warn if using production
    api_key = os.getenv('DEEPSEEK_TEST_API_KEY')
    if api_key:
        print("✓ Using DEEPSEEK_TEST_API_KEY")
    else:
        # Fallback to regular key but warn
        api_key = os.getenv('DEEPSEEK_API_KEY')
        if not api_key:
            print("ERROR: No API key found")
            print("Set DEEPSEEK_TEST_API_KEY for testing")
            print("Or DEEPSEEK_API_KEY (will use production credits)")
            sys.exit(1)

        print("⚠️  WARNING: Using DEEPSEEK_API_KEY (production)")
        print("   Consider setting DEEPSEEK_TEST_API_KEY instead")
        confirm = input("\nContinue with production key? (yes/no): ")
        if confirm.lower() != 'yes':
            print("Aborted")
            sys.exit(0)

    print(f"✓ API key loaded: {api_key[:10]}...")

    # Setup system
    print("\nSetting up O system...")

    # Create interactors
    echo = EchoInteractor()
    stdout = StdoutInteractor()

    mind = Mind({
        "echo": echo,
        "stdout": stdout
    })
    state = SystemState(tick=0, executions=[])
    transformer = DeepSeekTransformer(entity="@alice", api_key=api_key)
    body = Body(mind, state, transformers=[transformer])

    # Connect stdout to body (for tick access)
    stdout.body = body

    print("✓ Mind, State, Body, Transformer initialized")

    # Run one tick
    print("\nRunning Body.tick() - calling DeepSeek API...")
    print("(This will make a real API call)\n")

    await body.tick()

    # Check results
    log_file = Path("state/logs/log_0.json")
    if not log_file.exists():
        print("ERROR: No log file created")
        sys.exit(1)

    import json
    with open(log_file) as f:
        log_data = json.load(f)

    print("=" * 60)
    print("RESULTS")
    print("=" * 60)
    print(f"Tick: {log_data['tick']}")
    print(f"Executions: {len(log_data['executions'])}")
    print()

    if log_data['executions']:
        execution = log_data['executions'][0]
        print(f"Executor: {execution['executor']}")
        print(f"Command:  {execution['command']}")
        print(f"Output:   {execution['output']}")
        print()

        # Check if stdout file was created
        stdout_file = Path("memory/stdout/@alice.jsonl")
        if stdout_file.exists():
            print("✓ Stdout file created:")
            with open(stdout_file) as f:
                lines = f.readlines()
                for line in lines:
                    data = json.loads(line)
                    print(f"  Tick {data['tick']}: {data['content']}")
        else:
            print("(No stdout file created)")
            stdout_file = None

    print("\n" + "=" * 60)
    print("SUCCESS! Full cycle complete:")
    print("  Body.tick() → DeepSeekTransformer.poll()")
    print("  → DeepSeek API call → Command extraction")
    print("  → Mind.execute() → State.log()")
    print("=" * 60)

    # Note: NOT cleaning up - leaving files for inspection
    print("\nFiles preserved for inspection:")
    print(f"  - {log_file}")
    if stdout_file and stdout_file.exists():
        print(f"  - {stdout_file}")


if __name__ == "__main__":
    asyncio.run(main())
