#!/bin/bash
# UDOT Road Conditions VPS Deployment Script
# This script sets up systemd services for automated 24/7 operation

set -e  # Exit on error

echo "=========================================="
echo "UDOT Road Conditions VPS Deployment"
echo "=========================================="
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "ERROR: Please run as root (sudo ./deploy.sh)"
    exit 1
fi

# Get the actual project directory (where this script is located)
PROJECT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
echo "Project directory: $PROJECT_DIR"
echo ""

# Update service files with correct paths
echo "1. Updating service files with correct paths..."
sed -i "s|WorkingDirectory=.*|WorkingDirectory=$PROJECT_DIR|g" systemd/udot-api.service
sed -i "s|WorkingDirectory=.*|WorkingDirectory=$PROJECT_DIR|g" systemd/udot-detection.service

# Find Python 3 path
PYTHON_PATH=$(which python3)
echo "   Python path: $PYTHON_PATH"

# Find gunicorn path
GUNICORN_PATH=$(which gunicorn || echo "/usr/local/bin/gunicorn")
echo "   Gunicorn path: $GUNICORN_PATH"

# Update ExecStart paths
sed -i "s|ExecStart=/usr/bin/python3|ExecStart=$PYTHON_PATH|g" systemd/udot-detection.service
sed -i "s|ExecStart=/usr/local/bin/gunicorn|ExecStart=$GUNICORN_PATH|g" systemd/udot-api.service

echo "   ✓ Paths updated"
echo ""

# Install dependencies if needed
echo "2. Checking dependencies..."
if ! command -v gunicorn &> /dev/null; then
    echo "   Installing gunicorn..."
    pip3 install gunicorn
fi
echo "   ✓ Dependencies ready"
echo ""

# Copy service files to systemd directory
echo "3. Installing systemd services..."
cp systemd/udot-api.service /etc/systemd/system/
cp systemd/udot-detection.service /etc/systemd/system/
cp systemd/udot-detection.timer /etc/systemd/system/
echo "   ✓ Service files copied"
echo ""

# Reload systemd
echo "4. Reloading systemd daemon..."
systemctl daemon-reload
echo "   ✓ Daemon reloaded"
echo ""

# Enable and start API service
echo "5. Setting up API service..."
systemctl enable udot-api.service
systemctl restart udot-api.service
sleep 2

if systemctl is-active --quiet udot-api.service; then
    echo "   ✓ API service is running"
else
    echo "   ✗ API service failed to start"
    systemctl status udot-api.service --no-pager
    exit 1
fi
echo ""

# Enable and start timer (which manages the detection service)
echo "6. Setting up detection timer..."
systemctl enable udot-detection.timer
systemctl restart udot-detection.timer

if systemctl is-active --quiet udot-detection.timer; then
    echo "   ✓ Detection timer is active"
else
    echo "   ✗ Detection timer failed to start"
    systemctl status udot-detection.timer --no-pager
    exit 1
fi
echo ""

# Run detection once manually to populate initial data
echo "7. Running initial detection (this may take a few minutes)..."
systemctl start udot-detection.service
echo "   ✓ Detection started (check logs: journalctl -u udot-detection.service -f)"
echo ""

echo "=========================================="
echo "✓ Deployment Complete!"
echo "=========================================="
echo ""
echo "Services:"
echo "  • API Server:  http://$(hostname -I | awk '{print $1}'):5000"
echo "  • Detection:   Runs every 16 minutes"
echo ""
echo "Useful commands:"
echo "  • Check API status:      systemctl status udot-api"
echo "  • Check timer status:    systemctl list-timers udot-detection.timer"
echo "  • View API logs:         journalctl -u udot-api -f"
echo "  • View detection logs:   journalctl -u udot-detection -f"
echo "  • Restart API:           systemctl restart udot-api"
echo "  • Trigger detection now: systemctl start udot-detection"
echo ""
echo "Log files:"
echo "  • /var/log/udot-api.log"
echo "  • /var/log/udot-detection.log"
echo ""
