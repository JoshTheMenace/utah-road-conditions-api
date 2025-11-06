#!/usr/bin/env python3
"""
Google Drive OAuth Token Generator

Run this script on your LOCAL machine (with a browser) to generate the token.
Then copy the token.json file to your VPS.

This only needs to be done ONCE. The token will be refreshed automatically.
"""

import os
import sys
from pathlib import Path
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

# Scopes required for Drive upload
SCOPES = ['https://www.googleapis.com/auth/drive.file']


def generate_token(credentials_file='credentials.json', token_file='token.json'):
    """
    Generate OAuth token for Google Drive

    Args:
        credentials_file: OAuth client credentials (download from Google Cloud Console)
        token_file: Output file for the token
    """
    print("="*70)
    print("Google Drive OAuth Token Generator")
    print("="*70)

    # Check if credentials file exists
    if not Path(credentials_file).exists():
        print(f"\n✗ Error: {credentials_file} not found!")
        print("\nYou need to download OAuth client credentials:")
        print("1. Go to https://console.cloud.google.com/")
        print("2. Select your project")
        print("3. Go to 'APIs & Services' → 'Credentials'")
        print("4. Click 'Create Credentials' → 'OAuth client ID'")
        print("5. Choose 'Desktop app' as application type")
        print("6. Download the JSON file and save as 'credentials.json'")
        return False

    creds = None

    # Check if token already exists
    if Path(token_file).exists():
        print(f"\n⚠️  {token_file} already exists!")
        response = input("Regenerate token? (y/n): ")
        if response.lower() != 'y':
            print("Cancelled.")
            return True

        try:
            creds = Credentials.from_authorized_user_file(token_file, SCOPES)
        except Exception as e:
            print(f"Warning: Existing token is invalid: {e}")
            creds = None

    # Refresh or generate new token
    if creds and creds.valid:
        print("\n✓ Token is still valid!")
        return True

    if creds and creds.expired and creds.refresh_token:
        print("\nRefreshing expired token...")
        try:
            creds.refresh(Request())
            print("✓ Token refreshed!")
        except Exception as e:
            print(f"✗ Failed to refresh token: {e}")
            print("Will generate new token...")
            creds = None

    # Generate new token
    if not creds:
        print("\nGenerating new token...")
        print("A browser window will open for you to authorize the app.")
        print("\nIMPORTANT:")
        print("- Log in with your Google account")
        print("- Grant permission to access Google Drive")
        print("- You may see a warning that the app is unverified - click 'Advanced' → 'Go to app (unsafe)'")
        print("\nThis is safe - you're authorizing your own app!\n")

        input("Press Enter to open browser and start authorization...")

        try:
            flow = InstalledAppFlow.from_client_secrets_file(
                credentials_file,
                SCOPES
            )
            creds = flow.run_local_server(port=0)
            print("\n✓ Authorization successful!")
        except Exception as e:
            print(f"\n✗ Authorization failed: {e}")
            return False

    # Save token
    try:
        with open(token_file, 'w') as token:
            token.write(creds.to_json())
        print(f"\n✓ Token saved to: {token_file}")

        # Instructions for VPS
        print("\n" + "="*70)
        print("Next Steps - Copy Token to VPS")
        print("="*70)
        print(f"\n1. Copy {token_file} to your VPS:")
        print(f"   scp {token_file} user@your-vps:/home/josh/udot/")
        print("\n2. Test upload on VPS:")
        print("   python3 gdrive_uploader.py --credentials token.json")
        print("\n3. Enable automated hourly uploads:")
        print("   sudo systemctl enable --now udot-gdrive-upload.timer")
        print("\n" + "="*70)

        return True

    except Exception as e:
        print(f"\n✗ Failed to save token: {e}")
        return False


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(
        description='Generate Google Drive OAuth token for VPS',
        epilog='''
This script generates an OAuth token that allows your VPS to upload to Google Drive.

IMPORTANT: Run this on your LOCAL machine (not VPS) because it requires a browser.

Steps:
  1. Download OAuth credentials from Google Cloud Console
  2. Run this script: python generate_gdrive_token.py
  3. Authorize in browser when prompted
  4. Copy generated token.json to your VPS
  5. Done! The VPS can now upload to your Drive

The token will be automatically refreshed when needed.
        ''',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument('--credentials', type=str, default='credentials.json',
                       help='OAuth client credentials file (default: credentials.json)')
    parser.add_argument('--output', type=str, default='token.json',
                       help='Output token file (default: token.json)')

    args = parser.parse_args()

    success = generate_token(args.credentials, args.output)
    return 0 if success else 1


if __name__ == '__main__':
    exit(main())
