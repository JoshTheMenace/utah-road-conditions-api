# systemd Service Configuration

This directory contains systemd service files for running the UDOT road conditions system.

## Files

- `udot-api.service` - Flask API server (runs continuously)
- `udot-detection.service` - Detection script (triggered by timer)
- `udot-detection.timer` - Timer to run detection every 16 minutes

## Virtual Environment Setup

### How It Works

The service files use **absolute paths** to the virtual environment executables:

```ini
# Instead of activating the venv, we use direct paths:
ExecStart=/root/utah-road-conditions-api/venv/bin/python3 fast_pipeline.py
ExecStart=/root/utah-road-conditions-api/venv/bin/gunicorn -w 4 -b 0.0.0.0:5000 api_server:app
```

This approach:
- ✅ Works reliably with systemd
- ✅ No need to source/activate the venv
- ✅ All venv packages are automatically available
- ✅ Simpler and more explicit

### Alternative: Using Environment Variables

You *could* also set environment variables in the service file:

```ini
[Service]
Environment="PATH=/root/utah-road-conditions-api/venv/bin:/usr/bin:/bin"
Environment="VIRTUAL_ENV=/root/utah-road-conditions-api/venv"
ExecStart=/root/utah-road-conditions-api/venv/bin/python3 fast_pipeline.py
```

However, using the full path to the venv executable is simpler and more explicit.

## Why Not Activate the venv?

You might think to do this:

```ini
# ❌ DON'T DO THIS - it doesn't work well with systemd
ExecStart=/bin/bash -c 'source venv/bin/activate && python fast_pipeline.py'
```

Problems with this approach:
- More complex
- Harder to debug
- Shell interpretation issues
- Not the systemd way

## Manual Path Updates

If you move your project or use a different venv location, update these paths in the service files:

```bash
# Find all paths to update
grep -r "venv/bin" systemd/

# Example updates needed:
# 1. WorkingDirectory=/your/new/path
# 2. ExecStart=/your/new/path/venv/bin/python3
# 3. ExecStart=/your/new/path/venv/bin/gunicorn
```

Or just run `deploy.sh` which does this automatically!

## Testing Service Files Locally

Before installing, test the commands work:

```bash
# Test API
/path/to/venv/bin/gunicorn -w 4 -b 0.0.0.0:5000 api_server:app

# Test detection
/path/to/venv/bin/python3 fast_pipeline.py --max-cameras 5 --no-confirm
```

## Environment Variables in systemd

If you need to set other environment variables (API keys, config, etc.):

```ini
[Service]
Environment="API_KEY=your_key_here"
Environment="DEBUG=false"
Environment="DATA_DIR=/var/data/udot"

# Or load from a file:
EnvironmentFile=/etc/udot/config.env
```

Then access in Python:
```python
import os
api_key = os.getenv('API_KEY')
```

## Useful systemd Commands

```bash
# View service file
systemctl cat udot-api

# Edit service file
systemctl edit udot-api --full

# Reload after editing
systemctl daemon-reload
systemctl restart udot-api

# Check environment variables being used
systemctl show udot-api -p Environment
```
