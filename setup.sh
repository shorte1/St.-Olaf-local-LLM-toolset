#!/bin/bash
set -e

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WEB_DIR="$REPO_DIR/web"
VENV_DIR="$REPO_DIR/venv"
SYSTEMD_DIR="$HOME/.config/systemd/user"

# Create venv if it doesn't exist
if [ ! -d "$VENV_DIR" ]; then
    echo "Creating virtual environment at $VENV_DIR..."
    python3 -m venv "$VENV_DIR"
fi

# Install gunicorn into the venv if not already present
if [ ! -f "$VENV_DIR/bin/gunicorn" ]; then
    echo "Installing gunicorn into virtual environment..."
    "$VENV_DIR/bin/pip" install --quiet gunicorn
fi

GUNICORN="$VENV_DIR/bin/gunicorn"

if [ ! -f "$REPO_DIR/.env" ]; then
    echo "No .env found — creating one from .env.example..."
    cp "$REPO_DIR/.env.example" "$REPO_DIR/.env"
fi

source "$REPO_DIR/.env"

if [ -z "$SECRET_KEY" ] || [ "$SECRET_KEY" = "replace-with-generated-secret-key" ]; then
    SECRET_KEY="$(python3 -c 'import secrets; print(secrets.token_hex(24))')"
    sed -i "s|^SECRET_KEY=.*|SECRET_KEY=$SECRET_KEY|" "$REPO_DIR/.env"
    echo "Generated SECRET_KEY and saved to .env"
fi

if [ -z "$ADMIN_KEY" ] || [ "$ADMIN_KEY" = "replace-with-generated-admin-key" ]; then
    ADMIN_KEY="$(python3 -c 'import secrets; print(secrets.token_urlsafe(24))')"
    sed -i "s|^ADMIN_KEY=.*|ADMIN_KEY=$ADMIN_KEY|" "$REPO_DIR/.env"
    echo "Generated ADMIN_KEY and saved to .env"
fi

PODMAN="/usr/bin/podman"

if [ ! -x "$PODMAN" ]; then
    echo "Error: podman not found at $PODMAN"
    exit 1
fi

# Check that this user has subuid/subgid ranges (required for rootless containers)
if ! grep -q "^$USER:" /etc/subuid 2>/dev/null || ! grep -q "^$USER:" /etc/subgid 2>/dev/null; then
    echo ""
    echo "Error: rootless podman requires UID/GID mappings for '$USER'."
    echo "An admin must run the following once on this machine:"
    echo ""
    echo "  sudo usermod --add-subuids 100000-165535 --add-subgids 100000-165535 $USER"
    echo ""
    echo "Then re-run this setup script."
    exit 1
fi

# Migrate podman storage to current user namespace (safe to run repeatedly)
"$PODMAN" system migrate

# Create named network if missing
if ! "$PODMAN" network exists ollama-internal-network 2>/dev/null; then
    echo "Creating podman network: ollama-internal-network"
    "$PODMAN" network create ollama-internal-network
fi

# Create named volume if missing
if ! "$PODMAN" volume exists ollama 2>/dev/null; then
    echo "Creating podman volume: ollama"
    "$PODMAN" volume create ollama
fi

# Pull image if not already present
if ! "$PODMAN" image exists docker.io/ollama/ollama 2>/dev/null; then
    echo "Pulling docker.io/ollama/ollama (this may take a while)..."
    "$PODMAN" pull docker.io/ollama/ollama
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

echo "Starting ollama-container..."
systemctl --user start ollama-container.service

echo "Starting llm-web..."
systemctl --user start llm-web.service

loginctl enable-linger "$USER"

echo ""
echo "Setup complete. Services are running."
echo "  ollama-container: systemctl --user status ollama-container.service"
echo "  llm-web:          systemctl --user status llm-web.service"
