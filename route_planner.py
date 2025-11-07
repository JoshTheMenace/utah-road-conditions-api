#!/usr/bin/env python3
"""
Route planning with snow/hazard detection
Uses OSRM for routing and matches cameras to routes to detect hazardous conditions
"""

import requests
import json
from pathlib import Path
from math import radians, cos, sin, asin, sqrt
from typing import List, Dict, Tuple, Optional
from datetime import datetime


class RoutePlanner:
    """Plans routes and detects hazardous road conditions along the way"""

    def __init__(self, results_file: str = "data/fast_classified/classification_results.json"):
        self.results_file = Path(results_file)
        # Try multiple OSRM servers in order of preference
        self.osrm_servers = [
            "http://router.project-osrm.org",  # Public OSRM demo server (http not https)
            "https://routing.openstreetmap.de/routed-car"  # Alternative public server
        ]
        self.route_buffer_km = 0.5  # Search for cameras within 500m of route

    def haversine_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """
        Calculate the great circle distance between two points on Earth (in km)
        """
        # Convert to radians
        lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])

        # Haversine formula
        dlon = lon2 - lon1
        dlat = lat2 - lat1
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * asin(sqrt(a))
        km = 6371 * c  # Radius of earth in kilometers
        return km

    def point_to_line_distance(self, point: Tuple[float, float],
                              line_start: Tuple[float, float],
                              line_end: Tuple[float, float]) -> float:
        """
        Calculate minimum distance from a point to a line segment (in km)
        Uses simple perpendicular distance approximation
        """
        px, py = point
        x1, y1 = line_start
        x2, y2 = line_end

        # If line segment is actually a point
        if x1 == x2 and y1 == y2:
            return self.haversine_distance(py, px, y1, x1)

        # Calculate perpendicular distance
        # This is an approximation - for more accuracy could use proper geodesic calculations
        dx = x2 - x1
        dy = y2 - y1

        # Parameter t for closest point on line segment
        t = max(0, min(1, ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)))

        # Closest point on segment
        closest_x = x1 + t * dx
        closest_y = y1 + t * dy

        return self.haversine_distance(py, px, closest_y, closest_x)

    def get_route(self, origin: Tuple[float, float],
                  destination: Tuple[float, float],
                  alternatives: int = 3) -> Optional[Dict]:
        """
        Get route(s) from OSRM

        Args:
            origin: (longitude, latitude) tuple
            destination: (longitude, latitude) tuple
            alternatives: number of alternative routes to request

        Returns:
            OSRM response dict or None if failed
        """
        # OSRM expects lon,lat format
        origin_str = f"{origin[0]},{origin[1]}"
        dest_str = f"{destination[0]},{destination[1]}"

        # Try each server in order
        for server_url in self.osrm_servers:
            try:
                url = f"{server_url}/route/v1/driving/{origin_str};{dest_str}"
                params = {
                    'alternatives': min(alternatives, 3),  # OSRM max is usually 3
                    'steps': 'true',
                    'geometries': 'geojson',
                    'overview': 'full'
                }

                headers = {
                    'User-Agent': 'UDOT-Road-Conditions-API/1.0'
                }

                response = requests.get(url, params=params, headers=headers, timeout=15)
                response.raise_for_status()

                result = response.json()
                if result.get('code') == 'Ok':
                    return result

            except requests.exceptions.RequestException as e:
                print(f"Error with {server_url}: {e}")
                continue

        # If all servers failed, try simple straight-line fallback
        print("All routing servers failed, using simple fallback route")
        return self._create_simple_route(origin, destination)

    def _create_simple_route(self, origin: Tuple[float, float],
                           destination: Tuple[float, float]) -> Dict:
        """
        Create a simple straight-line route as fallback when OSRM is unavailable

        Args:
            origin: (longitude, latitude) tuple
            destination: (longitude, latitude) tuple

        Returns:
            Simple route dict in OSRM format
        """
        # Calculate approximate distance and duration
        distance_km = self.haversine_distance(
            origin[1], origin[0],
            destination[1], destination[0]
        )
        distance_m = distance_km * 1000

        # Estimate duration (assuming average speed of 90 km/h)
        duration_s = (distance_km / 90) * 3600

        # Create a simple 10-point path
        num_points = 10
        coords = []
        for i in range(num_points + 1):
            t = i / num_points
            lon = origin[0] + t * (destination[0] - origin[0])
            lat = origin[1] + t * (destination[1] - origin[1])
            coords.append([lon, lat])

        return {
            'code': 'Ok',
            'routes': [{
                'distance': distance_m,
                'duration': duration_s,
                'geometry': {
                    'type': 'LineString',
                    'coordinates': coords
                },
                'legs': [{
                    'distance': distance_m,
                    'duration': duration_s,
                    'steps': []
                }]
            }],
            'waypoints': [
                {'location': [origin[0], origin[1]]},
                {'location': [destination[0], destination[1]]}
            ]
        }

    def find_cameras_near_route(self, route_coords: List[List[float]],
                                cameras: Dict) -> List[Dict]:
        """
        Find cameras within buffer distance of route

        Args:
            route_coords: List of [lon, lat] coordinates defining the route
            cameras: Dictionary of camera data from classification results

        Returns:
            List of cameras near the route with distance info
        """
        nearby_cameras = []

        for cam_id, cam_data in cameras.items():
            # Skip failed classifications
            if cam_data.get('status') != 'success':
                continue

            cam_lat = cam_data['camera'].get('latitude')
            cam_lon = cam_data['camera'].get('longitude')

            if cam_lat is None or cam_lon is None:
                continue

            # Check distance to each segment of the route
            min_distance = float('inf')

            for i in range(len(route_coords) - 1):
                segment_start = (route_coords[i][0], route_coords[i][1])
                segment_end = (route_coords[i+1][0], route_coords[i+1][1])

                distance = self.point_to_line_distance(
                    (cam_lon, cam_lat),
                    segment_start,
                    segment_end
                )

                min_distance = min(min_distance, distance)

            # If camera is within buffer distance, include it
            if min_distance <= self.route_buffer_km:
                nearby_cameras.append({
                    'id': cam_id,
                    'name': cam_data['camera'].get('display_name', 'Unknown'),
                    'latitude': cam_lat,
                    'longitude': cam_lon,
                    'distance_km': round(min_distance, 3),
                    'classification': cam_data.get('classification', {}),
                    'safety_level': cam_data.get('classification', {}).get('safety_level', 'unknown')
                })

        # Sort by distance
        nearby_cameras.sort(key=lambda x: x['distance_km'])
        return nearby_cameras

    def score_route_safety(self, cameras: List[Dict]) -> Dict:
        """
        Score route based on camera safety levels

        Returns:
            Safety score and statistics
        """
        if not cameras:
            return {
                'score': 100,  # No data = assume safe
                'rating': 'unknown',
                'hazard_count': 0,
                'caution_count': 0,
                'safe_count': 0,
                'total_cameras': 0
            }

        # Count safety levels
        hazard_count = sum(1 for c in cameras if c['safety_level'] == 'hazardous')
        caution_count = sum(1 for c in cameras if c['safety_level'] == 'caution')
        safe_count = sum(1 for c in cameras if c['safety_level'] == 'safe')

        total = len(cameras)

        # Calculate score (0-100)
        # Hazardous: -30 points each
        # Caution: -10 points each
        # Safe: +5 points each
        score = 100 - (hazard_count * 30) - (caution_count * 10) + (safe_count * 5)
        score = max(0, min(100, score))  # Clamp to 0-100

        # Determine rating
        if hazard_count > 0:
            rating = 'hazardous'
        elif caution_count > total * 0.3:  # More than 30% caution
            rating = 'caution'
        elif safe_count > 0:
            rating = 'safe'
        else:
            rating = 'unknown'

        return {
            'score': round(score, 1),
            'rating': rating,
            'hazard_count': hazard_count,
            'caution_count': caution_count,
            'safe_count': safe_count,
            'total_cameras': total
        }

    def plan_route(self, origin: Tuple[float, float],
                   destination: Tuple[float, float],
                   alternatives: int = 3) -> Dict:
        """
        Plan route with hazard detection

        Args:
            origin: (longitude, latitude)
            destination: (longitude, latitude)
            alternatives: number of alternative routes

        Returns:
            Route plan with safety analysis
        """
        # Load camera data
        if not self.results_file.exists():
            return {
                'error': 'Camera data not available',
                'message': 'Run fast_pipeline.py first to generate camera data'
            }

        with open(self.results_file, 'r') as f:
            cameras = json.load(f)

        # Get routes from OSRM
        osrm_response = self.get_route(origin, destination, alternatives)

        if not osrm_response or osrm_response.get('code') != 'Ok':
            return {
                'error': 'Routing failed',
                'message': 'Could not calculate route. Check coordinates.'
            }

        # Analyze each route
        analyzed_routes = []

        for idx, route in enumerate(osrm_response.get('routes', [])):
            # Get route geometry (coordinates)
            coords = route['geometry']['coordinates']

            # Find cameras near this route
            nearby_cameras = self.find_cameras_near_route(coords, cameras)

            # Score route safety
            safety = self.score_route_safety(nearby_cameras)

            # Get hazardous cameras for detailed reporting
            hazardous_cameras = [
                c for c in nearby_cameras
                if c['safety_level'] == 'hazardous'
            ][:5]  # Top 5 most problematic

            analyzed_routes.append({
                'route_index': idx,
                'is_recommended': False,  # Will set after comparison
                'distance_km': round(route['distance'] / 1000, 2),
                'duration_min': round(route['duration'] / 60, 1),
                'safety': safety,
                'cameras_monitored': len(nearby_cameras),
                'hazardous_locations': hazardous_cameras,
                'geometry': route['geometry'],  # For map display
                'legs': route.get('legs', [])  # Turn-by-turn instructions
            })

        # Sort routes by safety score (highest = safest)
        analyzed_routes.sort(key=lambda x: x['safety']['score'], reverse=True)

        # Mark the safest route as recommended
        if analyzed_routes:
            analyzed_routes[0]['is_recommended'] = True

        return {
            'origin': {'longitude': origin[0], 'latitude': origin[1]},
            'destination': {'longitude': destination[0], 'latitude': destination[1]},
            'routes': analyzed_routes,
            'recommended_route': analyzed_routes[0] if analyzed_routes else None,
            'timestamp': datetime.now().isoformat(),
            'note': 'Routes scored based on real-time camera data. Lower scores indicate more hazardous conditions.'
        }


def geocode_address(address: str) -> Optional[Tuple[float, float]]:
    """
    Convert address to coordinates using Nominatim (OpenStreetMap)

    Args:
        address: Address string

    Returns:
        (longitude, latitude) tuple or None if failed
    """
    try:
        url = "https://nominatim.openstreetmap.org/search"
        params = {
            'q': address,
            'format': 'json',
            'limit': 1
        }
        headers = {
            'User-Agent': 'UDOT-Road-Conditions-API/1.0'
        }

        response = requests.get(url, params=params, headers=headers, timeout=10)
        response.raise_for_status()

        results = response.json()
        if results:
            return (float(results[0]['lon']), float(results[0]['lat']))

        return None

    except Exception as e:
        print(f"Geocoding error: {e}")
        return None


if __name__ == "__main__":
    # Test the route planner
    planner = RoutePlanner()

    # Example: Salt Lake City to Park City (common route with mountain pass)
    slc = (-111.8910, 40.7608)  # Salt Lake City
    park_city = (-111.4980, 40.6461)  # Park City

    print("Testing route planner...")
    print(f"From: Salt Lake City {slc}")
    print(f"To: Park City {park_city}")
    print()

    result = planner.plan_route(slc, park_city, alternatives=3)

    if 'error' in result:
        print(f"Error: {result['error']}")
        print(f"Message: {result['message']}")
    else:
        print(f"Found {len(result['routes'])} route(s)")
        print()
        for route in result['routes']:
            print(f"Route {route['route_index'] + 1}:")
            print(f"  Recommended: {'Yes' if route['is_recommended'] else 'No'}")
            print(f"  Distance: {route['distance_km']} km")
            print(f"  Duration: {route['duration_min']} min")
            print(f"  Safety Score: {route['safety']['score']}/100 ({route['safety']['rating']})")
            print(f"  Cameras monitored: {route['cameras_monitored']}")
            print(f"  Hazards detected: {route['safety']['hazard_count']}")
            if route['hazardous_locations']:
                print(f"  Hazardous locations:")
                for cam in route['hazardous_locations']:
                    print(f"    - {cam['name']} ({cam['distance_km']} km from route)")
            print()
