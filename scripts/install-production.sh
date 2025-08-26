#!/bin/bash

# Production installation script for Web Database Migration Assistant
set -e

# Configuration
INSTALL_DIR="/opt/migration-assistant"
SERVICE_USER="migration"
SERVICE_GROUP="migration"
PYTHON_VERSION="3.11"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
    exit 1
}

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   error "This script must be run as root"
fi

log "Starting Web Database Migration Assistant production installation..."

# Install system dependencies
log "Installing system dependencies..."
apt-get update
apt-get install -y \
    python3.11 \
    python3.11-venv \
    python3.11-dev \
    python3-pip \
    openssh-client \
    rsync \
    mysql-client \
    postgresql-client \
    redis-tools \
    curl \
    wget \
    git \
    build-essential \
    golang-go

# Create service user
log "Creating service user..."
if ! id "$SERVICE_USER" &>/dev/null; then
    useradd --system --create-home --shell /bin/bash --home-dir "$INSTALL_DIR" "$SERVICE_USER"
    usermod -a -G "$SERVICE_GROUP" "$SERVICE_USER" 2>/dev/null || groupadd "$SERVICE_GROUP" && usermod -a -G "$SERVICE_GROUP" "$SERVICE_USER"
fi

# Create installation directory
log "Setting up installation directory..."
mkdir -p "$INSTALL_DIR"
mkdir -p "$INSTALL_DIR/logs"
mkdir -p "$INSTALL_DIR/backups"
mkdir -p "$INSTALL_DIR/config"

# Copy application files
log "Copying application files..."
cp -r . "$INSTALL_DIR/"
chown -R "$SERVICE_USER:$SERVICE_GROUP" "$INSTALL_DIR"

# Create Python virtual environment
log "Creating Python virtual environment..."
sudo -u "$SERVICE_USER" python3.11 -m venv "$INSTALL_DIR/venv"

# Install Python dependencies
log "Installing Python dependencies..."
sudo -u "$SERVICE_USER" "$INSTALL_DIR/venv/bin/pip" install --upgrade pip
sudo -u "$SERVICE_USER" "$INSTALL_DIR/venv/bin/pip" install -e "$INSTALL_DIR"

# Build Go binaries
log "Building Go performance engine..."
cd "$INSTALL_DIR/go-engine"
sudo -u "$SERVICE_USER" go mod download
sudo -u "$SERVICE_USER" go build -o "$INSTALL_DIR/bin/migration-engine" ./cmd/migration-engine
cd -

# Install systemd service
log "Installing systemd service..."
cp "$INSTALL_DIR/scripts/migration-assistant.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable migration-assistant

# Create default configuration
log "Creating default configuration..."
cat > "$INSTALL_DIR/config/config.yaml" << EOF
migration:
  backup:
    enabled: true
    retention_days: 30
    storage_path: "$INSTALL_DIR/backups"
  performance:
    engine: "go"
    max_concurrent_transfers: 5
  security:
    encrypt_transfers: true
    validate_checksums: true
  logging:
    level: "INFO"
    file: "$INSTALL_DIR/logs/migration-assistant.log"
EOF

chown "$SERVICE_USER:$SERVICE_GROUP" "$INSTALL_DIR/config/config.yaml"

# Set up log rotation
log "Setting up log rotation..."
cat > /etc/logrotate.d/migration-assistant << EOF
$INSTALL_DIR/logs/*.log {
    daily
    missingok
    rotate 30
    compress
    delaycompress
    notifempty
    create 644 $SERVICE_USER $SERVICE_GROUP
    postrotate
        systemctl reload migration-assistant
    endscript
}
EOF

# Create CLI wrapper
log "Creating CLI wrapper..."
cat > /usr/local/bin/migration-assistant << EOF
#!/bin/bash
exec sudo -u $SERVICE_USER $INSTALL_DIR/venv/bin/python -m migration_assistant.cli.main "\$@"
EOF
chmod +x /usr/local/bin/migration-assistant

# Start service
log "Starting migration assistant service..."
systemctl start migration-assistant

# Verify installation
log "Verifying installation..."
sleep 5
if systemctl is-active --quiet migration-assistant; then
    log "✓ Service is running successfully"
else
    error "✗ Service failed to start. Check logs: journalctl -u migration-assistant"
fi

# Display status
log "Installation completed successfully!"
echo
echo "Service Status:"
systemctl status migration-assistant --no-pager -l
echo
echo "Configuration file: $INSTALL_DIR/config/config.yaml"
echo "Log files: $INSTALL_DIR/logs/"
echo "Backup directory: $INSTALL_DIR/backups/"
echo
echo "Usage:"
echo "  CLI: migration-assistant --help"
echo "  API: curl http://localhost:8000/health"
echo "  Logs: journalctl -u migration-assistant -f"
echo
log "Web Database Migration Assistant is ready for production use!"