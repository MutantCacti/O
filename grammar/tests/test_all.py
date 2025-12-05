#!/usr/bin/env python3
"""
Test runner for all grammar tests

Discovers and runs all test_*.py files in grammar/tests/
Usage:
    python test_all.py              # Run all tests
    python test_all.py -v           # Verbose
    python test_all.py --cov        # With coverage
"""

import sys
import subprocess
from pathlib import Path

def main():
    """Run all tests in tests/ directory"""
    tests_dir = Path(__file__).parent
    venv_pytest = tests_dir.parent.parent / 'venv' / 'bin' / 'pytest'

    # Check if pytest exists in venv
    if not venv_pytest.exists():
        print("Error: pytest not found in venv")
        print("Run: python3 -m venv ../../venv && ../../venv/bin/pip install pytest pytest-cov")
        sys.exit(1)

    # Build pytest command
    cmd = [str(venv_pytest), str(tests_dir)]

    # Add user arguments
    if len(sys.argv) > 1:
        cmd.extend(sys.argv[1:])
    else:
        # Default: verbose with short traceback
        cmd.extend(['-v', '--tb=short'])

    # Run pytest
    result = subprocess.run(cmd)
    sys.exit(result.returncode)


if __name__ == '__main__':
    main()
