#!/bin/bash

if [ -z "$1" ]; then
    echo "Usage: ./review.sh <paper.txt> [follow-up question]"
    exit 1
fi

PAPER_FILE="$1"
QUESTION="$2"

python3 - << EOF
import json
import requests
import sys

with open("$PAPER_FILE", "r") as f:
    paper = f.read()

if "$QUESTION":
    prompt = "$QUESTION" + "\n\nPaper:\n" + paper
else:
    prompt = "Please review the following paper:\n\n" + paper

response = requests.post(
    "http://localhost:11435/api/generate",
    json={"model": "writing-consultant", "prompt": prompt},
    stream=True,
    timeout=300
)

for line in response.iter_lines():
    if line:
        try:
            token = json.loads(line).get("response", "")
            print(token, end="", flush=True)
        except:
            continue
print()
EOF
