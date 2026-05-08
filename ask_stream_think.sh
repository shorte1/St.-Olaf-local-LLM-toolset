#!/bin/bash

SHOW_THINKING=false
while getopts "t" flag; do
        case $flag in
                t) SHOW_THINKING=true ;;
        esac
done
shift $((OPTIND - 1))

if ! podman ps --format "{{.Names}}" | grep -q "ollama-internal"; then
        echo "Starting container..."
        podman start ollama-internal
        until curl -s http://localhost:11435 > /dev/null; do
                sleep 1
        done
        echo "Container started"
fi

if [ -n "$2" ]; then
        FILE_CONTENTS=$(cat "$2")
        FULL_PROMPT="$1\n\nDocument contents:\n$FILE_CONTENTS"
else
        FULL_PROMPT="$1"
fi

curl -s http://localhost:11435/api/generate \
  -d "{\"model\": \"deepseek-r1:32b\", \"prompt\": \"$FULL_PROMPT\"}" \
  | python3 -c "
import sys
import json
import re

show_thinking = '$SHOW_THINKING' == 'true'
in_think = False
buffer = ''

for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    try:
        data = json.loads(line)
        token = data.get('response', '')
        buffer += token

        if '<think>' in buffer:
            in_think = True
        if '</think>' in buffer:
            in_think = False
            buffer = buffer.split('</think>')[-1]
            continue

        if not in_think or show_thinking:
            print(token, end='', flush=True)
    except json.JSONDecodeError:
        continue
print()
"
