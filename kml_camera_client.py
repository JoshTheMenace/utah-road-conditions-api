# kml_camera_client.py
import requests
import xml.etree.ElementTree as ET
from pathlib import Path
from PIL import Image
from io import BytesIO
import json

class KMLCameraClient:
    def __init__(self):
        self.kml_url = "https://www.udottraffic.utah.gov/ForecastView/KmlFile.aspx?kmlFileType=Camera"
        self.session = requests.Session()
    
    def fetch_cameras_from_kml(self, include_all=False):
        """Parse KML file to get camera info with direct image URLs

        Args:
            include_all: If True, return all cameras. If False, only return online cameras with image URLs.
        """
        print("Fetching camera data from KML...")
        response = self.session.get(self.kml_url, timeout=10)
        response.raise_for_status()

        # Parse XML
        root = ET.fromstring(response.content)

        # Define namespace
        ns = {
            'kml': 'http://www.opengis.net/kml/2.2',
            'gx': 'http://www.google.com/kml/ext/2.2'
        }

        cameras = []

        # Find all Placemark elements
        for placemark in root.findall('.//kml:Placemark', ns):
            camera = {}

            # Get name
            name_elem = placemark.find('kml:name', ns)
            if name_elem is not None:
                camera['name'] = name_elem.text

            # Get extended data
            extended_data = placemark.find('.//kml:ExtendedData/kml:SchemaData', ns)
            if extended_data is not None:
                for simple_data in extended_data.findall('kml:SimpleData', ns):
                    field_name = simple_data.get('name')
                    field_value = simple_data.text

                    if field_name == 'IntId':
                        camera['id'] = field_value
                    elif field_name == 'ImageUrl':
                        camera['image_url'] = field_value
                    elif field_name == 'IsOnline':
                        camera['is_online'] = field_value == 'True'
                    elif field_name == 'IsMediaReady':
                        camera['is_media_ready'] = field_value == 'True'
                    elif field_name == 'DisplayName':
                        camera['display_name'] = field_value
                    elif field_name == 'TrafficDirection':
                        camera['direction'] = field_value

            # Get coordinates
            coords_elem = placemark.find('.//kml:coordinates', ns)
            if coords_elem is not None:
                coords = coords_elem.text.strip().split(',')
                if len(coords) >= 2:
                    camera['longitude'] = float(coords[0])
                    camera['latitude'] = float(coords[1])

            # Filter based on include_all parameter
            if include_all:
                # Include all cameras that have coordinates
                if 'latitude' in camera and 'longitude' in camera:
                    cameras.append(camera)
            else:
                # Only include online cameras with image URLs (original behavior)
                if camera.get('image_url') and camera.get('is_online'):
                    cameras.append(camera)

        print(f"✓ Found {len(cameras)} cameras in KML")
        return cameras
    
    def test_image(self, image_url):
        """Test if image URL returns actual camera image"""
        try:
            response = self.session.get(image_url, timeout=10)
            if response.status_code != 200:
                return False, "HTTP error"
            
            # Check if it's actually an image
            try:
                img = Image.open(BytesIO(response.content))
                width, height = img.size
                
                # Check image size (placeholder images are usually tiny)
                if width < 200 or height < 150:
                    return False, "Image too small"
                
                # Check file size (placeholder images are usually very small)
                if len(response.content) < 5000:  # Less than 5KB
                    return False, "File too small"
                
                return True, f"{width}x{height}"
            except Exception as e:
                return False, f"Not an image: {e}"
        except Exception as e:
            return False, str(e)
    
    def find_working_cameras(self, max_cameras=30, priority_keywords=None):
        """Find cameras with working image feeds"""
        if priority_keywords is None:
            priority_keywords = [
                'i-15', 'i-80', 'i-70', 'i-84',  # Interstates
                'us-', 'sr-',  # Highways
                'canyon', 'summit', 'pass', 'mountain', 'mp', 'mile'
            ]
        
        all_cameras = self.fetch_cameras_from_kml()
        
        # Filter for online cameras with media ready
        online_cameras = [
            cam for cam in all_cameras 
            if cam.get('is_online') and cam.get('is_media_ready')
        ]
        
        print(f"Found {len(online_cameras)} cameras marked as online with media ready")
        
        # Sort by priority
        def camera_score(cam):
            score = 0
            name = cam.get('display_name', '').lower()
            
            for keyword in priority_keywords:
                if keyword in name:
                    score += 10
            
            return score
        
        sorted_cameras = sorted(online_cameras, key=camera_score, reverse=True)
        
        working_cameras = []
        tested = 0
        
        print(f"\n--- Testing cameras for actual images ---")
        
        for cam in sorted_cameras:
            if len(working_cameras) >= max_cameras:
                break
            
            tested += 1
            image_url = cam['image_url']
            
            print(f"\n#{tested}. Testing: {cam['display_name'][:60]}")
            print(f"   URL: {image_url}")
            
            is_working, info = self.test_image(image_url)
            
            if is_working:
                print(f"   ✓ Working! {info}")
                working_cameras.append(cam)
            else:
                print(f"   ✗ Failed: {info}")
        
        print(f"\n✓ Found {len(working_cameras)} working cameras out of {tested} tested")
        return working_cameras
    
    def download_image(self, camera, output_dir="data/kml_cameras"):
        """Download image from camera"""
        output_path = Path(output_dir) / f"{camera['id']}.jpg"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            response = self.session.get(camera['image_url'], timeout=10)
            response.raise_for_status()
            
            with open(output_path, 'wb') as f:
                f.write(response.content)
            
            return output_path
        except Exception as e:
            print(f"Error downloading {camera['id']}: {e}")
            return None


def main():
    """Find and download working camera images"""
    client = KMLCameraClient()
    
    # Find working cameras
    working_cameras = client.find_working_cameras(max_cameras=30)
    
    if not working_cameras:
        print("\n❌ No working cameras found!")
        return
    
    # Download images
    print(f"\n--- Downloading {len(working_cameras)} camera images ---")
    for cam in working_cameras:
        print(f"Downloading: {cam['display_name'][:60]}...")
        path = client.download_image(cam)
        if path:
            print(f"  ✓ Saved to {path}")
    
    # Save camera list
    with open('working_cameras_kml.json', 'w') as f:
        json.dump(working_cameras, f, indent=2)
    
    print(f"\n✓ Complete! {len(working_cameras)} working cameras")
    print("✓ Camera list saved to working_cameras_kml.json")
    print("✓ Images saved to data/kml_cameras/")


if __name__ == "__main__":
    main()
