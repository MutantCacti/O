#!/bin/bash
# Camp 2 Integration Test - O solving coursework

cd /home/mutant/csilw/O-0.1.0.0

# Clean up any previous runs
pkill -f "app.py" 2>/dev/null
pkill -f "deepseek" 2>/dev/null
rm -rf transformers/fifos/@solver 2>/dev/null
rm -rf output/*.md 2>/dev/null
sleep 1

echo "=== Starting O ==="
venv/bin/python app.py --max-ticks 300 --tick-interval 2 &
O_PID=$!
sleep 3

echo "=== Spawning @solver ==="
echo '\spawn @solver ---' > transformers/fifos/@root/input.fifo
sleep 2

echo "=== Starting DeepSeek transformer ==="
PROMPT='You are @solver, an autonomous problem-solving agent. Your task:

## Question 1: Turing Machine (10 marks)
Design a 3-tape Turing Machine for binary multiplication mod 2^n:
- Tape 1: binary number a (n bits)
- Tape 2: binary number b (n bits)
- Tape 3: output a*b mod 2^n (n bits)

Example: n=6, a=20 (010100), b=42 (101010). Result: 8 (001000) since 20*42=840, 840 mod 64 = 8.

Tasks:
1. Design the TM - describe states, transitions, algorithm
2. Analyze running time - is it efficient?

## Question 2: RSA Breaking (10 marks)
Public key: n = 10000003700006700002479, e = 65537
Ciphertext: c = 185243452602769190899

The key has an exploitable weakness. Tasks:
1. Identify the weakness and explain your attack
2. Factor n to find p and q
3. Compute private key d
4. Decrypt c to find m (encodes a famous computer scientist name)

## Instructions
Use \publish to save your solutions:
- \publish q1_solution.md [your TM design] ---
- \publish q2_solution.md [your RSA solution] ---

CRITICAL: Commands end with "---". Do NOT use "---" anywhere in your content (no horizontal rules, no separators). Use "===" or "***" instead if you need visual separators.

Work step by step. Show your reasoning. Begin.'

venv/bin/python -m transformers.deepseek @solver "$PROMPT" &
TRANS_PID=$!

echo ""
echo "=== Test running ==="
echo "O PID: $O_PID"
echo "Transformer PID: $TRANS_PID"
echo ""
echo "Monitor with: watch -n 2 'ls -la output/ 2>/dev/null; cat output/*.md 2>/dev/null | head -100'"
echo "Or use: ./transformers/bin/o-shell @solver"
echo ""
echo "Press Ctrl+C to stop"

# Wait for transformer to finish or user interrupt
trap "echo 'Stopping...'; kill $TRANS_PID $O_PID 2>/dev/null; exit 0" INT TERM
wait $TRANS_PID

echo "=== Transformer finished ==="
echo "Stopping O..."
kill $O_PID 2>/dev/null
wait $O_PID 2>/dev/null

echo ""
echo "=== Results ==="
ls -la output/ 2>/dev/null
echo ""
for f in output/*.md; do
    if [ -f "$f" ]; then
        echo "--- $f ---"
        cat "$f"
        echo ""
    fi
done
