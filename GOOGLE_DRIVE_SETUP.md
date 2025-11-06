# Google Drive Setup Guide

This guide will help you set up Google Drive integration to automatically upload road condition images every hour.

## Overview

The system will:
- Compress images with JPEG quality 85 (good balance of size/quality)
- Resize images to max 1920px (maintains quality, reduces size)
- Upload to Google Drive in organized folders: `UDOT-Road-Conditions/YYYY-MM-DD/`
- Run automatically every hour via systemd timer
- Skip already uploaded images (no duplicates)

## Prerequisites

- A Google account
- Access to Google Cloud Console
- systemd (for automated uploads)

## Step 1: Create Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Click "Select a project" → "New Project"
3. Enter project name (e.g., "UDOT Road Conditions")
4. Click "Create"

## Step 2: Enable Google Drive API

1. In the Google Cloud Console, go to "APIs & Services" → "Library"
2. Search for "Google Drive API"
3. Click on it and click "Enable"

## Step 3: Create Service Account (Recommended for Servers)

**Service accounts are best for automated server uploads** because they don't require user interaction.

### 3.1 Create Service Account

1. Go to "APIs & Services" → "Credentials"
2. Click "Create Credentials" → "Service Account"
3. Enter name (e.g., "udot-uploader")
4. Click "Create and Continue"
5. Skip optional steps (no roles needed for Drive API with file scope)
6. Click "Done"

### 3.2 Create and Download Key

1. Click on the service account you just created
2. Go to "Keys" tab
3. Click "Add Key" → "Create new key"
4. Choose "JSON" format
5. Click "Create"
6. The key file will download automatically

### 3.3 Install Key on Server

```bash
# Copy the downloaded JSON file to your server
scp ~/Downloads/your-project-xxxxx.json user@your-server:/home/josh/udot/credentials.json

# Set permissions (important for security!)
chmod 600 /home/josh/udot/credentials.json
```

### 3.4 Share Google Drive Folder with Service Account

⚠️ **Important**: Service accounts have their own Drive storage. To upload to YOUR Google Drive:

1. In Google Drive, create a folder (e.g., "UDOT-Road-Conditions")
2. Right-click folder → "Share"
3. Add the service account email (found in the JSON file, looks like: `udot-uploader@project-name.iam.gserviceaccount.com`)
4. Give it "Editor" permissions
5. Click "Share"

Now uploads will go to your personal Drive folder!

## Step 4: Test the Uploader

```bash
# Activate virtual environment
cd /home/josh/udot
source venv/bin/activate

# Install dependencies (if not already done)
pip install -r requirements.txt

# Test upload with service account
python gdrive_uploader.py --service-account --credentials credentials.json

# Test with custom settings
python gdrive_uploader.py \
    --service-account \
    --credentials credentials.json \
    --quality 90 \
    --max-size 2048
```

### Expected Output

```
======================================================================
UDOT Image Upload to Google Drive
======================================================================
✓ Authenticated with Google Drive

Setting up folder structure in 'UDOT-Road-Conditions'...
  Using existing folder: UDOT-Road-Conditions
  Created folder: 2025-11-06

Found 150 images to process
Compression settings: quality=85, max_size=1920px

[1/150] ✓ Uploaded: camera_001.jpg (850KB → 320KB, -62%)
[2/150] ✓ Uploaded: camera_002.jpg (920KB → 350KB, -62%)
...
```

## Step 5: Set Up Automated Hourly Uploads

The systemd service is already created. Just enable it:

```bash
# Copy service files (if using deploy.sh, this is automatic)
sudo cp systemd/udot-gdrive-upload.service /etc/systemd/system/
sudo cp systemd/udot-gdrive-upload.timer /etc/systemd/system/

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

### "Authentication failed"

- Check that credentials.json exists and has correct permissions
- Verify the service account email is correct
- Make sure Google Drive API is enabled in your project

### "No images found"

- Check that classification is running: `sudo systemctl status udot-detection.service`
- Verify images exist: `ls -la /home/josh/udot/data/fast_classified/`
- Check the image directory path in the service file

### "Error uploading: 403 Forbidden"

- The service account doesn't have permission
- Share the Google Drive folder with the service account email
- Give it "Editor" permissions

### "Error uploading: Quota exceeded"

- Check your Google Drive storage space
- Each day produces ~50-150 MB of compressed images
- Consider deleting old images or upgrading storage

### Service not running

```bash
# Check service status
sudo systemctl status udot-gdrive-upload.service

# Check timer status
sudo systemctl status udot-gdrive-upload.timer

# Restart timer
sudo systemctl restart udot-gdrive-upload.timer

# View errors
sudo journalctl -u udot-gdrive-upload.service -p err
```

## Storage Estimates

With default compression (quality=85, max_size=1920):

- Average compressed image: 200-400 KB
- Daily uploads (assuming 500 cameras): 100-200 MB
- Monthly storage: ~3-6 GB
- Yearly storage: ~36-72 GB

Google Drive free tier: 15 GB
- Enough for ~2-5 months of images
- Consider upgrading to Google One (100GB for $1.99/month)

## Security Notes

1. **Protect credentials.json**
   ```bash
   chmod 600 /home/josh/udot/credentials.json
   ```

2. **Use service accounts** (not OAuth user tokens) for servers

3. **Limit permissions**: Only enable "Google Drive API" with file scope

4. **Rotate keys** periodically:
   - Delete old keys in Google Cloud Console
   - Create new keys and update credentials.json

## Alternative: OAuth User Authentication

If you prefer to use your personal Google account instead of a service account:

1. Create OAuth 2.0 Client ID in Google Cloud Console
2. Download client credentials as `credentials.json`
3. Run initial authentication:
   ```bash
   python gdrive_uploader.py --credentials credentials.json
   ```
4. Follow the browser authentication flow
5. This creates a `token.json` file with your access token
6. Use `token.json` instead of service account credentials

⚠️ OAuth tokens expire and require manual renewal, so **service accounts are recommended for servers**.

## Support

For issues or questions:
- Check logs: `sudo journalctl -u udot-gdrive-upload.service`
- Verify credentials: `cat credentials.json | grep client_email`
- Test manually: `python gdrive_uploader.py --service-account`
- Check Google Drive API quota: https://console.cloud.google.com/apis/dashboard
