#!/bin/bash
# Clean up O runtime artifacts (NOT source code)

cd /home/mutant/csilw/O-0.1.0.0

# Kill any running processes
pkill -f "app.py" 2>/dev/null
pkill -f "deepseek" 2>/dev/null

# Remove runtime OUTPUT only
rm -rf output/*

# Remove runtime MEMORY data only (not the directory)
rm -rf memory/wake/
rm -rf memory/listen/
rm -rf memory/spaces/
rm -rf memory/stdout/
rm -rf memory/incoming/
rm -rf memory/read/

# Remove entity FIFOs except @root
find transformers/fifos -mindepth 1 -maxdepth 1 -type d ! -name '@root' -exec rm -rf {} \;

# Clear @root FIFOs
rm -f transformers/fifos/@root/*.fifo 2>/dev/null

echo "Cleaned runtime data (output/, memory/*, non-root fifos)"
