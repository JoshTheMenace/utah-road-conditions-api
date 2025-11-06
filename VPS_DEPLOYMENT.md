# VPS Deployment Guide - UDOT Road Conditions

This guide explains how to set up automated 24/7 operation on your Ubuntu VPS.

## Overview

The system consists of three components:
1. **API Server** - Flask/Gunicorn server running continuously on port 5000
2. **Detection Script** - Runs every 16 minutes to fetch and classify camera images
3. **Google Drive Upload** - Runs every hour to backup compressed images to Google Drive

## Architecture

- **systemd services** manage both processes (not tmux/screen)
- **systemd timer** triggers detection every 16 minutes
- **Auto-restart** on failure
- **Persistent logs** in `/var/log/`
- **Starts on boot** automatically

## Quick Setup

### 1. Clone Repository on VPS

```bash
cd ~
git clone <your-repo-url> utah-road-conditions-api
cd utah-road-conditions-api
```

### 2. Set Up Virtual Environment (Recommended)

```bash
# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Install dependencies in venv
pip install -r requirements.txt

# Gunicorn will be installed automatically by deploy.sh
```

**Note:** The deployment script automatically detects and uses your `venv` directory if it exists. The systemd services will use the venv's Python and packages.

### 3. Deploy Services

```bash
# Run deployment script (as root)
sudo ./deploy.sh
```

That's it! The script will:
- Install systemd service files
- Configure paths automatically
- Start API server
- Enable detection timer
- Run initial detection

### 4. Set Up Google Drive (Optional)

To automatically backup images to Google Drive with compression:

```bash
# See detailed setup guide
cat GOOGLE_DRIVE_SETUP.md

# Or skip to quick steps:
# 1. Create service account in Google Cloud Console
# 2. Download credentials.json to project directory
# 3. Share Google Drive folder with service account email
# 4. Deploy the upload service
sudo ./deploy.sh
```

### 5. Verify Deployment

```bash
# Check API is running
curl http://localhost:5000

# Check services status
systemctl status udot-api
systemctl status udot-detection.timer
systemctl status udot-gdrive-upload.timer  # If Google Drive is set up

# See when next runs will occur
systemctl list-timers
```

## Virtual Environment Details

The systemd services are configured to use your virtual environment automatically:

- **API Service**: Uses `/path/to/project/venv/bin/gunicorn`
- **Detection Service**: Uses `/path/to/project/venv/bin/python3`

This means:
- All packages installed in your venv are available to the services
- No need to activate the venv manually - systemd uses the full path
- Your system Python remains unaffected

The `deploy.sh` script automatically:
1. Detects if a `venv` directory exists
2. Updates service files with the correct venv paths
3. Falls back to system Python if no venv is found

## Manual Setup (Alternative)

If you prefer manual setup:

### 1. Update Service Files

Edit `systemd/udot-api.service` and `systemd/udot-detection.service`:
- Change `WorkingDirectory` to your actual path (e.g., `/root/utah-road-conditions-api`)
- Update `User` if not running as root
- Update paths in `ExecStart` to use your venv:
  - For API: `/your/path/venv/bin/gunicorn`
  - For detection: `/your/path/venv/bin/python3`

### 2. Copy Service Files

```bash
sudo cp systemd/udot-api.service /etc/systemd/system/
sudo cp systemd/udot-detection.service /etc/systemd/system/
sudo cp systemd/udot-detection.timer /etc/systemd/system/
sudo cp systemd/udot-gdrive-upload.service /etc/systemd/system/  # Optional
sudo cp systemd/udot-gdrive-upload.timer /etc/systemd/system/    # Optional
```

### 3. Enable and Start

```bash
# Reload systemd
sudo systemctl daemon-reload

# Enable and start API
sudo systemctl enable udot-api.service
sudo systemctl start udot-api.service

# Enable and start timer
sudo systemctl enable udot-detection.timer
sudo systemctl start udot-detection.timer

# Run detection once to populate initial data
sudo systemctl start udot-detection.service

# Optional: Enable Google Drive upload timer
sudo systemctl enable udot-gdrive-upload.timer
sudo systemctl start udot-gdrive-upload.timer
```

## Configuration

### Adjust Detection Settings

Edit `systemd/udot-detection.service` to customize:

```ini
ExecStart=/usr/bin/python3 fast_pipeline.py \
    --max-cameras 900 \          # Number of cameras (adjust for VPS resources)
    --workers 4 \                # Parallel workers (2-8, lower = less CPU)
    --highways-only \            # Optional: only major highways
    --no-confirm \               # Required: skip prompt
    --min-confidence 0.5         # Hazard detection threshold
```

**Resource-constrained VPS?**
- Use `--max-cameras 200` for faster runs
- Use `--workers 2` to reduce CPU load
- Add `--highways-only` to focus on major roads

After changes:
```bash
sudo systemctl daemon-reload
sudo systemctl restart udot-detection.timer
```

### Adjust Detection Interval

Edit `systemd/udot-detection.timer`:

```ini
# Change from 16 minutes to 30 minutes:
OnUnitActiveSec=30min
```

Then reload:
```bash
sudo systemctl daemon-reload
sudo systemctl restart udot-detection.timer
```

### Configure Google Drive Upload (Optional)

See `GOOGLE_DRIVE_SETUP.md` for detailed instructions.

Quick configuration of compression settings:

```bash
# Edit service file
sudo nano /etc/systemd/system/udot-gdrive-upload.service

# Adjust compression settings in ExecStart line:
# --quality 85      # JPEG quality (1-100, 85 is good balance)
# --max-size 1920   # Max dimension in pixels

# Reload and restart
sudo systemctl daemon-reload
sudo systemctl restart udot-gdrive-upload.timer
```

### Change API Port

Edit `systemd/udot-api.service`:

```ini
# Change from port 5000 to 8080:
ExecStart=/usr/local/bin/gunicorn -w 4 -b 0.0.0.0:8080 api_server:app
```

Then restart:
```bash
sudo systemctl daemon-reload
sudo systemctl restart udot-api
```

## Monitoring

### View Logs

```bash
# API logs (live)
journalctl -u udot-api -f

# Detection logs (live)
journalctl -u udot-detection -f

# Google Drive upload logs (live)
journalctl -u udot-gdrive-upload -f

# Or from log files
tail -f /var/log/udot-api.log
tail -f /var/log/udot-detection.log
tail -f /var/log/udot-gdrive-upload.log

# View last 100 lines
journalctl -u udot-api -n 100
journalctl -u udot-gdrive-upload -n 100
```

### Check Status

```bash
# Check if services are running
systemctl status udot-api
systemctl status udot-detection.timer
systemctl status udot-gdrive-upload.timer  # If enabled

# See timer schedule
systemctl list-timers

# Check last detection run
systemctl status udot-detection

# Check last Google Drive upload
systemctl status udot-gdrive-upload

# Check if API is responding
curl http://localhost:5000/api/stats
```

### Common Commands

```bash
# Restart API
sudo systemctl restart udot-api

# Stop detection timer
sudo systemctl stop udot-detection.timer

# Start detection timer
sudo systemctl start udot-detection.timer

# Run detection immediately (one-time)
sudo systemctl start udot-detection

# Run Google Drive upload immediately
sudo systemctl start udot-gdrive-upload

# Disable auto-start on boot
sudo systemctl disable udot-api
sudo systemctl disable udot-detection.timer
sudo systemctl disable udot-gdrive-upload.timer  # If enabled

# Re-enable auto-start
sudo systemctl enable udot-api
sudo systemctl enable udot-detection.timer
sudo systemctl enable udot-gdrive-upload.timer  # If enabled
```

## Troubleshooting

### API Not Starting

```bash
# Check detailed logs
journalctl -u udot-api -xe

# Common issues:
# - Port 5000 already in use: Change port in service file
# - Missing dependencies: pip3 install -r requirements.txt
# - Wrong working directory: Update WorkingDirectory in service file
```

### Detection Not Running

```bash
# Check timer status
systemctl list-timers udot-detection.timer

# Check last run
journalctl -u udot-detection -n 50

# Common issues:
# - Timer not enabled: systemctl enable udot-detection.timer
# - Service fails: Check logs for errors (missing models, etc.)
# - Wrong paths: Update WorkingDirectory in service file
```

### High Resource Usage

If VPS is struggling:

```bash
# Reduce cameras
sudo nano /etc/systemd/system/udot-detection.service
# Change --max-cameras to a lower number (e.g., 100-200)

# Reduce workers
# Change --workers to 2

# Reload and restart
sudo systemctl daemon-reload
sudo systemctl restart udot-detection.timer
```

### Models Not Downloading

Detection will download ~600MB models on first run:

```bash
# Check available disk space
df -h

# Check detection logs
journalctl -u udot-detection -f

# Manually test model download
python3 fast_pipeline.py --max-cameras 5 --no-confirm
```

## Testing

### Test Detection Locally

```bash
# Test with small number of cameras
python3 fast_pipeline.py --max-cameras 10 --no-confirm

# Check results
cat data/fast_classified/classification_results.json | head
```

### Test API Locally

```bash
# Run API in foreground for debugging
python3 api_server.py

# Or with gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 api_server:app

# Test endpoints
curl http://localhost:5000/
curl http://localhost:5000/api/stats
```

## Firewall

If API isn't accessible from outside:

```bash
# Allow port 5000 (Ubuntu/UFW)
sudo ufw allow 5000/tcp

# Or for firewalld
sudo firewall-cmd --permanent --add-port=5000/tcp
sudo firewall-cmd --reload
```

## Updating Code

When you update the code:

```bash
# Pull latest changes
git pull

# Restart services
sudo systemctl restart udot-api
sudo systemctl restart udot-detection.timer

# Check everything is working
systemctl status udot-api
systemctl list-timers udot-detection.timer
```

## Google Drive Upload

The system can automatically backup classified images to Google Drive every hour with compression. This is optional but recommended for:

- **Backup**: Keep copies of images in cloud storage
- **Compression**: Reduces file size by ~60-70% with minimal quality loss
- **Organization**: Images organized by date in folders

### Key Features

- **Compression**: JPEG quality 85 (excellent balance)
- **Resizing**: Max 1920px (keeps most images unchanged)
- **Smart upload**: Skips already uploaded images
- **Organized folders**: `UDOT-Road-Conditions/YYYY-MM-DD/`
- **Hourly schedule**: Runs every hour automatically

### Setup

See `GOOGLE_DRIVE_SETUP.md` for complete instructions. Quick version:

1. Create service account in Google Cloud Console
2. Download credentials.json
3. Share Google Drive folder with service account
4. Enable the upload timer

### Storage Requirements

With default compression (quality=85, max_size=1920):

- Average image: 200-400 KB
- Daily uploads: ~100-200 MB (for 500 cameras)
- Monthly: ~3-6 GB
- Yearly: ~36-72 GB

Google Drive free tier (15 GB) is enough for 2-5 months of images.

## Uninstall

To completely remove:

```bash
# Stop and disable services
sudo systemctl stop udot-api
sudo systemctl stop udot-detection.timer
sudo systemctl stop udot-gdrive-upload.timer  # If enabled
sudo systemctl disable udot-api
sudo systemctl disable udot-detection.timer
sudo systemctl disable udot-gdrive-upload.timer  # If enabled

# Remove service files
sudo rm /etc/systemd/system/udot-api.service
sudo rm /etc/systemd/system/udot-detection.service
sudo rm /etc/systemd/system/udot-detection.timer
sudo rm /etc/systemd/system/udot-gdrive-upload.service  # If exists
sudo rm /etc/systemd/system/udot-gdrive-upload.timer    # If exists

# Reload systemd
sudo systemctl daemon-reload
```

## Why systemd Instead of tmux?

**systemd advantages:**
- ✓ Auto-restart on crash
- ✓ Auto-start on boot
- ✓ Proper logging
- ✓ Resource limits
- ✓ No manual session management
- ✓ Industry standard for Linux services

**tmux/screen downsides:**
- ✗ Manual session management
- ✗ No auto-restart
- ✗ Sessions can die
- ✗ Not suitable for production
- ✗ No built-in logging

## Support

For issues:
1. Check logs: `journalctl -u udot-api -f`
2. Check service status: `systemctl status udot-api`
3. Test manually: `python3 api_server.py`
4. Verify dependencies: `pip3 list | grep -E 'flask|transformers|torch'`
