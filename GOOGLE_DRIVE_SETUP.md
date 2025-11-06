# Google Drive Setup Guide

This guide will help you set up Google Drive integration to automatically upload road condition images every hour.

## Overview

The system will:
- Compress images with JPEG quality 85 (good balance of size/quality)
- Resize images to max 1920px (maintains quality, reduces size)
- Upload to Google Drive in organized folders: `UDOT-Road-Conditions/YYYY-MM-DD/`
- Run automatically every hour via systemd timer
- Skip already uploaded images (no duplicates)

## Important: OAuth Authentication

This system uses **OAuth user authentication**, which means:
- ✅ Works with regular (free) Google accounts
- ✅ Uploads go to YOUR Google Drive
- ✅ No storage quota issues
- ⚠️ Requires one-time setup on a machine with a browser
- ✅ Once set up, works automatically on VPS forever

**Note**: Service accounts don't work with free Google accounts - they require Google Workspace and Shared Drives.

## Prerequisites

- A Google account
- Access to Google Cloud Console
- A computer with a web browser (for initial setup)
- systemd (for automated uploads on VPS)

## Step 1: Create Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Click "Select a project" → "New Project"
3. Enter project name (e.g., "UDOT Road Conditions")
4. Click "Create"

## Step 2: Enable Google Drive API

1. In the Google Cloud Console, go to "APIs & Services" → "Library"
2. Search for "Google Drive API"
3. Click on it and click "Enable"

## Step 3: Create OAuth Client ID

### 3.1 Configure OAuth Consent Screen (First Time Only)

1. Go to "APIs & Services" → "OAuth consent screen"
2. Choose "External" (for personal accounts)
3. Click "Create"
4. Fill in required fields:
   - App name: "UDOT Road Conditions Uploader"
   - User support email: Your email
   - Developer contact: Your email
5. Click "Save and Continue"
6. Skip "Scopes" (click "Save and Continue")
7. Add yourself as a test user:
   - Click "Add Users"
   - Enter your Gmail address
   - Click "Save and Continue"
8. Click "Back to Dashboard"

### 3.2 Create OAuth Client ID

1. Go to "APIs & Services" → "Credentials"
2. Click "Create Credentials" → "OAuth client ID"
3. Choose "Desktop app" as application type
4. Enter name: "UDOT Desktop Client"
5. Click "Create"
6. Click "Download JSON" to download the credentials file
7. Save it as `credentials.json`

## Step 4: Generate OAuth Token (On Local Machine)

**This step must be done on your LOCAL computer** (not VPS) because it requires a browser.

### 4.1 Copy Files to Local Machine

If you've cloned the repo, you already have the script. Otherwise:

```bash
# Clone repo on your local machine
git clone https://github.com/YourUsername/utah-road-conditions-api.git
cd utah-road-conditions-api

# Or download just the token generator:
curl -O https://raw.githubusercontent.com/YourUsername/utah-road-conditions-api/main/generate_gdrive_token.py
```

### 4.2 Install Requirements Locally

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install Google API packages
pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib
```

### 4.3 Generate Token

```bash
# Make sure credentials.json is in the current directory
python generate_gdrive_token.py
```

This will:
1. Open your web browser automatically
2. Ask you to log in to Google
3. Show a warning "Google hasn't verified this app"
   - Click "Advanced" → "Go to UDOT Road Conditions Uploader (unsafe)"
   - This is safe - you're authorizing your own app!
4. Ask for permission to access your Drive
   - Click "Allow"
5. Generate `token.json` file

### 4.4 Expected Output

```
======================================================================
Google Drive OAuth Token Generator
======================================================================

Generating new token...
A browser window will open for you to authorize the app.

Press Enter to open browser and start authorization...

✓ Authorization successful!
✓ Token saved to: token.json

======================================================================
Next Steps - Copy Token to VPS
======================================================================

1. Copy token.json to your VPS:
   scp token.json user@your-vps:/home/josh/udot/

2. Test upload on VPS:
   python3 gdrive_uploader.py --token token.json

3. Enable automated hourly uploads:
   sudo systemctl enable --now udot-gdrive-upload.timer

======================================================================
```

## Step 5: Copy Token to VPS

```bash
# From your local machine
scp token.json user@your-vps:/home/josh/udot/

# Set permissions on VPS
ssh user@your-vps
chmod 600 /home/josh/udot/token.json
```

## Step 6: Test Upload on VPS

```bash
# SSH into your VPS
ssh user@your-vps

# Navigate to project
cd /home/josh/udot
source venv/bin/activate

# Install dependencies (if not already done)
pip install -r requirements.txt

# Test upload
python gdrive_uploader.py --token token.json
```

### Expected Output

```
======================================================================
UDOT Image Upload to Google Drive
======================================================================
✓ Authenticated with Google Drive

Setting up folder structure in 'UDOT-Road-Conditions'...
  Created folder: UDOT-Road-Conditions
  Created folder: 2025-11-06

Found 150 images to process
Compression settings: quality=85, max_size=1920px

[1/150] ✓ Uploaded: camera_001.jpg (850KB → 320KB, -62%)
[2/150] ✓ Uploaded: camera_002.jpg (920KB → 350KB, -62%)
...
```

If you see "✓ Authenticated with Google Drive" and images uploading, you're all set!

## Step 7: Enable Automated Hourly Uploads

```bash
# Copy service files (if not already done)
sudo cp systemd/udot-gdrive-upload.service /etc/systemd/system/
sudo cp systemd/udot-gdrive-upload.timer /etc/systemd/system/

# Update paths in service file if needed
sudo nano /etc/systemd/system/udot-gdrive-upload.service
# Make sure WorkingDirectory and ExecStart paths are correct

# Reload systemd
sudo systemctl daemon-reload

# Enable and start timer
sudo systemctl enable udot-gdrive-upload.timer
sudo systemctl start udot-gdrive-upload.timer

# Check timer status
sudo systemctl status udot-gdrive-upload.timer
sudo systemctl list-timers udot-gdrive*

# Check most recent upload
sudo systemctl status udot-gdrive-upload.service
sudo journalctl -u udot-gdrive-upload.service -n 50
```

## Token Refresh

The OAuth token will **automatically refresh** when it expires. The script handles this for you:

- Initial token is valid for ~1 week
- After expiration, it refreshes automatically using a refresh token
- Refresh token is valid for 6 months (with regular use, it never expires)
- No manual intervention needed!

If the token somehow becomes invalid:
1. Run `python generate_gdrive_token.py` again on your local machine
2. Copy new `token.json` to VPS
3. Restart the service: `sudo systemctl restart udot-gdrive-upload.service`

## Compression Settings

The default settings provide excellent quality while reducing file size by ~60-70%:

- **Quality**: 85 (out of 100)
  - 85-90: Excellent quality, minimal visible loss
  - 70-80: Good quality, more compression
  - 90-95: Near-lossless, larger files

- **Max Size**: 1920px (Full HD)
  - Most traffic cams are 1280x720 or 1920x1080
  - Larger images are resized proportionally
  - Smaller images are kept as-is

### Adjust Settings

Edit `/etc/systemd/system/udot-gdrive-upload.service`:

```ini
# Higher quality (less compression)
ExecStart=... --quality 90 --max-size 2048

# More compression (smaller files)
ExecStart=... --quality 75 --max-size 1280
```

Then reload:
```bash
sudo systemctl daemon-reload
sudo systemctl restart udot-gdrive-upload.timer
```

## Folder Organization

Images are automatically organized:

```
Google Drive/
└── UDOT-Road-Conditions/
    ├── 2025-11-06/
    │   ├── camera_001.jpg
    │   ├── camera_002.jpg
    │   └── ...
    ├── 2025-11-07/
    │   └── ...
    └── 2025-11-08/
        └── ...
```

Each day gets its own folder with the date (YYYY-MM-DD format).

## Monitoring

### Check Upload Logs

```bash
# View recent uploads
sudo journalctl -u udot-gdrive-upload.service -f

# View last 100 lines
sudo journalctl -u udot-gdrive-upload.service -n 100

# View logs for specific date
sudo journalctl -u udot-gdrive-upload.service --since "2025-11-06"
```

### Check Timer Status

```bash
# When is next upload?
sudo systemctl list-timers udot-gdrive*

# Timer details
systemctl status udot-gdrive-upload.timer
```

### Manual Upload

```bash
# Trigger upload manually
sudo systemctl start udot-gdrive-upload.service

# Watch it run
sudo journalctl -u udot-gdrive-upload.service -f
```

## Troubleshooting

### "Token file not found"

**Problem**: token.json doesn't exist on VPS

**Solution**:
1. Run `python generate_gdrive_token.py` on your local machine
2. Copy token.json to VPS: `scp token.json user@vps:/home/josh/udot/`

### "Authentication failed"

**Problem**: Token is invalid or expired and can't be refreshed

**Solution**:
1. Regenerate token on local machine: `python generate_gdrive_token.py`
2. Copy new token.json to VPS
3. Restart service: `sudo systemctl restart udot-gdrive-upload.service`

### "No images found"

**Problem**: Image directory is empty or wrong path

**Solution**:
- Check that classification is running: `sudo systemctl status udot-detection.service`
- Verify images exist: `ls -la /home/josh/udot/data/fast_classified/`
- Check the image directory path in the service file

### "Browser doesn't open" (when generating token)

**Problem**: Running on a server or SSH session

**Solution**:
- You MUST run `generate_gdrive_token.py` on your LOCAL machine with a desktop/browser
- Never try to generate the token directly on the VPS
- Generate locally, then copy token.json to VPS

### Token keeps expiring

**Problem**: Token refresh failing

**Solution**:
1. Check if you added yourself as a test user in OAuth consent screen
2. Regenerate token and make sure to approve all permissions
3. Check logs: `sudo journalctl -u udot-gdrive-upload.service -p err`

### "Error 403: Service Accounts do not have storage quota"

**Problem**: You're trying to use a service account (not OAuth)

**Solution**:
- Service accounts only work with Google Workspace Shared Drives
- For personal Google accounts, use OAuth (follow this guide)
- Make sure you're using `--token token.json`, NOT `--service-account`

## Storage Estimates

With default compression (quality=85, max_size=1920):

- Average compressed image: 200-400 KB
- Daily uploads (assuming 500 cameras): 100-200 MB
- Monthly storage: ~3-6 GB
- Yearly storage: ~36-72 GB

Google Drive free tier: 15 GB
- Enough for ~2-5 months of images
- Consider upgrading to Google One (100GB for $1.99/month)
- Or periodically delete old images

## Security Notes

1. **Protect token.json**
   ```bash
   chmod 600 /home/josh/udot/token.json
   ```

2. **Keep credentials.json private** (only needed on local machine)

3. **Limit permissions**: Only enable "Google Drive API" with file scope

4. **Remove test users**: After setup, you can remove yourself from test users in OAuth consent screen (but app will keep working)

5. **Revoke access** anytime at: https://myaccount.google.com/permissions

## FAQ

### Do I need Google Workspace?

**No!** This method works with free personal Google accounts. Service accounts require Workspace, but OAuth (this guide) works with any Google account.

### How long is the token valid?

The access token expires after ~1 hour, but it auto-refreshes. The refresh token lasts 6 months, but with regular use (hourly uploads), it never expires.

### Can I use the same token on multiple servers?

Yes! You can copy token.json to multiple VPS instances. They'll all upload to the same Google Drive folder.

### What if I change my Google password?

Your token will still work. Changing password doesn't invalidate OAuth tokens. You can revoke tokens manually at https://myaccount.google.com/permissions if needed.

### Can I use this for other folders?

Yes! Just change the `--folder` parameter:
```bash
python gdrive_uploader.py --token token.json --folder "My-Custom-Folder"
```

## Support

For issues or questions:
- Check logs: `sudo journalctl -u udot-gdrive-upload.service`
- Verify token exists: `ls -la /home/josh/udot/token.json`
- Test manually: `python gdrive_uploader.py --token token.json`
- Check Google Drive API quota: https://console.cloud.google.com/apis/dashboard
- Verify OAuth consent: https://console.cloud.google.com/apis/credentials/consent
