#!/bin/bash
set -e

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WEB_DIR="$REPO_DIR/web"
SYSTEMD_DIR="$HOME/.config/systemd/user"
GUNICORN="$(which gunicorn 2>/dev/null || echo '')"

# Validate environment
if [ -z "$GUNICORN" ]; then
    echo "Error: gunicorn not found. Install it with: pip install gunicorn"
    exit 1
fi

if [ ! -f "$REPO_DIR/.env" ]; then
    echo "Error: .env file not found. Copy .env.example to .env and fill in your values."
    exit 1
fi

source "$REPO_DIR/.env"

if [ -z "$SECRET_KEY" ] || [ "$SECRET_KEY" = "replace-with-generated-secret-key" ]; then
    echo "Error: SECRET_KEY is not set in .env"
    exit 1
fi

if [ -z "$ADMIN_KEY" ] || [ "$ADMIN_KEY" = "replace-with-generated-admin-key" ]; then
    echo "Error: ADMIN_KEY is not set in .env"
    exit 1
fi

mkdir -p "$SYSTEMD_DIR"

cat > "$SYSTEMD_DIR/llm-web.service" << EOF
[Unit]
Description=LLM Web Interface
After=ollama-container.service
Wants=ollama-container.service

[Service]
Type=simple
WorkingDirectory=$WEB_DIR
ExecStart=$GUNICORN -w 4 -b 0.0.0.0:8080 --timeout 300 app:app
Restart=always
RestartSec=10
Environment="SECRET_KEY=$SECRET_KEY"
Environment="ADMIN_KEY=$ADMIN_KEY"
StandardOutput=append:$HOME/llm-web.log
StandardError=append:$HOME/llm-web.log

[Install]
WantedBy=default.target
EOF

cat > "$SYSTEMD_DIR/ollama-container.service" << EOF
[Unit]
Description=Ollama Container
After=default.target

[Service]
Type=simple
ExecStartPre=-/usr/bin/podman rm -f ollama-internal
ExecStart=/usr/bin/podman run --name ollama-internal \\
  -v ollama:/root/.ollama \\
  -p 11435:11434 \\
  --network ollama-internal-network \\
  --device nvidia.com/gpu=all \\
  docker.io/ollama/ollama
ExecStop=/usr/bin/podman stop ollama-internal
Restart=always
RestartSec=10

[Install]
WantedBy=default.target
EOF

systemctl --user daemon-reload
systemctl --user enable ollama-container.service llm-web.service

echo ""
echo "Service files written to $SYSTEMD_DIR"
echo "Run the following to start:"
echo "  systemctl --user start ollama-container.service"
echo "  systemctl --user start llm-web.service"
echo "  loginctl enable-linger \$USER"
