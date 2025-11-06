#!/usr/bin/env python3
"""
Google Drive Uploader for UDOT Road Condition Images
Compresses and uploads classified images to Google Drive every hour
"""

import os
import json
from pathlib import Path
from datetime import datetime
from PIL import Image
import io
import argparse

# Google Drive API imports
from google.oauth2.credentials import Credentials
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from googleapiclient.errors import HttpError


class ImageCompressor:
    """Compress images for efficient storage"""

    def __init__(self, quality=85, max_dimension=1920):
        """
        Args:
            quality: JPEG quality (1-100, default 85 for good balance)
            max_dimension: Maximum width/height (default 1920)
        """
        self.quality = quality
        self.max_dimension = max_dimension

    def compress_image(self, image_path):
        """
        Compress image and return bytes

        Args:
            image_path: Path to image file

        Returns:
            BytesIO object with compressed image, or None if failed
        """
        try:
            # Open image
            img = Image.open(image_path)

            # Convert to RGB if necessary (handle PNG, etc.)
            if img.mode in ('RGBA', 'LA', 'P'):
                # Create white background
                background = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                background.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
                img = background
            elif img.mode != 'RGB':
                img = img.convert('RGB')

            # Resize if too large
            if max(img.size) > self.max_dimension:
                ratio = self.max_dimension / max(img.size)
                new_size = tuple(int(dim * ratio) for dim in img.size)
                img = img.resize(new_size, Image.Resampling.LANCZOS)

            # Compress to JPEG in memory
            output = io.BytesIO()
            img.save(output, format='JPEG', quality=self.quality, optimize=True)
            output.seek(0)

            return output

        except Exception as e:
            print(f"Error compressing {image_path}: {e}")
            return None


class GoogleDriveUploader:
    """Upload images to Google Drive"""

    def __init__(self, credentials_path='token.json'):
        """
        Initialize Google Drive uploader

        Args:
            credentials_path: Path to OAuth token file (token.json)
        """
        self.credentials_path = credentials_path
        self.service = None
        self.folder_id = None

    def authenticate(self):
        """Authenticate with Google Drive using OAuth token"""
        try:
            # Check if token file exists
            if not Path(self.credentials_path).exists():
                print(f"✗ Token file not found: {self.credentials_path}")
                print("\nYou need to generate an OAuth token first:")
                print("1. On your LOCAL machine (with browser), run:")
                print("   python generate_gdrive_token.py")
                print("2. Follow the browser authentication flow")
                print("3. Copy the generated token.json to your VPS")
                print("\nSee GOOGLE_DRIVE_SETUP.md for detailed instructions.")
                return False

            # Load OAuth token
            creds = Credentials.from_authorized_user_file(
                self.credentials_path,
                scopes=['https://www.googleapis.com/auth/drive.file']
            )

            # Check if token needs refresh
            from google.auth.transport.requests import Request
            if creds and creds.expired and creds.refresh_token:
                print("Refreshing expired token...")
                creds.refresh(Request())
                # Save refreshed token
                with open(self.credentials_path, 'w') as token:
                    token.write(creds.to_json())
                print("✓ Token refreshed")

            self.service = build('drive', 'v3', credentials=creds)
            print("✓ Authenticated with Google Drive")
            return True

        except Exception as e:
            print(f"✗ Authentication failed: {e}")
            print("\nPlease regenerate your OAuth token:")
            print("1. On your LOCAL machine, run: python generate_gdrive_token.py")
            print("2. Copy token.json to VPS")
            print("\nSee GOOGLE_DRIVE_SETUP.md for help.")
            return False

    def get_or_create_folder(self, folder_name, parent_id=None):
        """
        Get existing folder or create new one

        Args:
            folder_name: Name of folder
            parent_id: Parent folder ID (None for root)

        Returns:
            Folder ID or None if failed
        """
        try:
            # Search for existing folder
            query = f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
            if parent_id:
                query += f" and '{parent_id}' in parents"

            results = self.service.files().list(
                q=query,
                spaces='drive',
                fields='files(id, name)'
            ).execute()

            files = results.get('files', [])

            if files:
                # Folder exists
                folder_id = files[0]['id']
                print(f"  Using existing folder: {folder_name}")
                return folder_id

            # Create new folder
            file_metadata = {
                'name': folder_name,
                'mimeType': 'application/vnd.google-apps.folder'
            }

            if parent_id:
                file_metadata['parents'] = [parent_id]

            folder = self.service.files().create(
                body=file_metadata,
                fields='id'
            ).execute()

            print(f"  Created folder: {folder_name}")
            return folder.get('id')

        except Exception as e:
            print(f"Error creating folder {folder_name}: {e}")
            return None

    def setup_folder_structure(self, base_folder='UDOT-Road-Conditions'):
        """
        Create folder structure: UDOT-Road-Conditions/YYYY-MM-DD/

        Returns:
            Folder ID for today's folder
        """
        try:
            # Create/get base folder
            base_id = self.get_or_create_folder(base_folder)
            if not base_id:
                return None

            # Create/get date folder (YYYY-MM-DD)
            date_folder = datetime.now().strftime('%Y-%m-%d')
            date_id = self.get_or_create_folder(date_folder, parent_id=base_id)

            self.folder_id = date_id
            return date_id

        except Exception as e:
            print(f"Error setting up folders: {e}")
            return None

    def file_exists(self, filename, folder_id):
        """Check if file already exists in folder"""
        try:
            query = f"name='{filename}' and '{folder_id}' in parents and trashed=false"
            results = self.service.files().list(
                q=query,
                spaces='drive',
                fields='files(id, name)'
            ).execute()

            files = results.get('files', [])
            return len(files) > 0

        except Exception as e:
            print(f"Error checking file existence: {e}")
            return False

    def upload_image(self, image_bytes, filename, folder_id=None):
        """
        Upload compressed image to Google Drive

        Args:
            image_bytes: BytesIO object with image data
            filename: Name for the file
            folder_id: Folder to upload to (None for root)

        Returns:
            File ID or None if failed
        """
        try:
            # Check if already uploaded
            target_folder = folder_id or self.folder_id
            if target_folder and self.file_exists(filename, target_folder):
                print(f"  ⊘ Skipping (already exists): {filename}")
                return None

            # Create file metadata
            file_metadata = {'name': filename}
            if target_folder:
                file_metadata['parents'] = [target_folder]

            # Upload
            media = MediaIoBaseUpload(
                image_bytes,
                mimetype='image/jpeg',
                resumable=True
            )

            file = self.service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id'
            ).execute()

            return file.get('id')

        except HttpError as e:
            print(f"Error uploading {filename}: {e}")
            return None


def process_and_upload_images(
    image_dir='data/fast_classified',
    credentials_path='token.json',
    quality=85,
    max_dimension=1920,
    base_folder='UDOT-Road-Conditions'
):
    """
    Main function to compress and upload images

    Args:
        image_dir: Directory containing images
        credentials_path: Path to OAuth token file (token.json)
        quality: JPEG compression quality (1-100)
        max_dimension: Maximum image dimension
        base_folder: Base folder name in Google Drive
    """
    print("="*70)
    print("UDOT Image Upload to Google Drive")
    print("="*70)

    # Initialize components
    compressor = ImageCompressor(quality=quality, max_dimension=max_dimension)
    uploader = GoogleDriveUploader(credentials_path=credentials_path)

    # Authenticate
    if not uploader.authenticate():
        print("\n✗ Failed to authenticate with Google Drive")
        return False

    # Setup folders
    print(f"\nSetting up folder structure in '{base_folder}'...")
    if not uploader.setup_folder_structure(base_folder):
        print("✗ Failed to set up folders")
        return False

    # Find images to upload
    image_dir = Path(image_dir)
    if not image_dir.exists():
        print(f"✗ Image directory not found: {image_dir}")
        return False

    # Get all image files
    image_extensions = {'.jpg', '.jpeg', '.png'}
    image_files = [
        f for f in image_dir.glob('*')
        if f.suffix.lower() in image_extensions and f.is_file()
    ]

    if not image_files:
        print(f"\n⚠ No images found in {image_dir}")
        return True

    print(f"\nFound {len(image_files)} images to process")
    print(f"Compression settings: quality={quality}, max_size={max_dimension}px")
    print()

    # Process and upload each image
    uploaded = 0
    skipped = 0
    failed = 0
    total_original_size = 0
    total_compressed_size = 0

    for i, image_path in enumerate(image_files, 1):
        try:
            # Get original size
            original_size = image_path.stat().st_size
            total_original_size += original_size

            # Compress
            compressed = compressor.compress_image(image_path)
            if not compressed:
                print(f"[{i}/{len(image_files)}] ✗ Failed to compress: {image_path.name}")
                failed += 1
                continue

            compressed_size = compressed.getbuffer().nbytes
            total_compressed_size += compressed_size
            compression_ratio = (1 - compressed_size / original_size) * 100

            # Upload with compressed name
            filename = f"{image_path.stem}.jpg"  # Use .jpg extension
            file_id = uploader.upload_image(compressed, filename)

            if file_id:
                print(f"[{i}/{len(image_files)}] ✓ Uploaded: {image_path.name} "
                      f"({original_size/1024:.0f}KB → {compressed_size/1024:.0f}KB, "
                      f"-{compression_ratio:.0f}%)")
                uploaded += 1
            elif file_id is None and uploader.file_exists(filename, uploader.folder_id):
                skipped += 1
            else:
                print(f"[{i}/{len(image_files)}] ✗ Failed to upload: {image_path.name}")
                failed += 1

        except Exception as e:
            print(f"[{i}/{len(image_files)}] ✗ Error processing {image_path.name}: {e}")
            failed += 1

    # Summary
    print("\n" + "="*70)
    print("Upload Summary")
    print("="*70)
    print(f"✓ Uploaded:     {uploaded}")
    print(f"⊘ Skipped:      {skipped} (already exist)")
    print(f"✗ Failed:       {failed}")
    print(f"\nTotal images:   {len(image_files)}")

    if total_original_size > 0 and total_compressed_size > 0:
        total_saved = total_original_size - total_compressed_size
        total_ratio = (total_saved / total_original_size) * 100
        print(f"\nCompression:")
        print(f"  Original:     {total_original_size/1024/1024:.1f} MB")
        print(f"  Compressed:   {total_compressed_size/1024/1024:.1f} MB")
        print(f"  Saved:        {total_saved/1024/1024:.1f} MB ({total_ratio:.0f}%)")

    print("="*70)

    return failed == 0


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Upload compressed UDOT images to Google Drive',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  # Upload with default settings (uses token.json)
  python gdrive_uploader.py

  # Use custom token file
  python gdrive_uploader.py --token my-token.json

  # Custom compression settings
  python gdrive_uploader.py --quality 90 --max-size 2048

  # Different image directory
  python gdrive_uploader.py --image-dir data/custom_classified

Setup:
  1. On LOCAL machine: python generate_gdrive_token.py
  2. Copy token.json to VPS
  3. Run this script on VPS
        '''
    )

    parser.add_argument('--image-dir', type=str, default='data/fast_classified',
                       help='Directory containing images (default: data/fast_classified)')
    parser.add_argument('--token', type=str, default='token.json',
                       help='Path to OAuth token file (default: token.json)')
    parser.add_argument('--quality', type=int, default=85,
                       help='JPEG compression quality 1-100 (default: 85)')
    parser.add_argument('--max-size', type=int, default=1920,
                       help='Maximum image dimension in pixels (default: 1920)')
    parser.add_argument('--folder', type=str, default='UDOT-Road-Conditions',
                       help='Base folder name in Google Drive (default: UDOT-Road-Conditions)')

    args = parser.parse_args()

    # Validate quality
    if not 1 <= args.quality <= 100:
        print("Error: Quality must be between 1 and 100")
        return 1

    # Run upload
    success = process_and_upload_images(
        image_dir=args.image_dir,
        credentials_path=args.token,
        quality=args.quality,
        max_dimension=args.max_size,
        base_folder=args.folder
    )

    return 0 if success else 1


if __name__ == '__main__':
    exit(main())
