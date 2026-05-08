#!/bin/bash

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
import sys, json

for line in sys.stdin:
    try:
        print(json.loads(line).get('response',''), end='', flush=True)
    except:
        continue
print()
"
