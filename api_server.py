#!/usr/bin/env python3
"""
Lightweight Flask API server for VPS
Serves classification results JSON with CORS headers
"""

from flask import Flask, jsonify, send_file, request
from flask_cors import CORS
from pathlib import Path
import json
from datetime import datetime
import os
from route_planner import RoutePlanner, geocode_address

app = Flask(__name__)

# Enable CORS for all routes (allows Vercel to fetch)
CORS(app)

# Path to results file
RESULTS_FILE = Path("data/fast_classified/classification_results.json")

# Initialize route planner
route_planner = RoutePlanner(str(RESULTS_FILE))

@app.route("/")
def home():
    """Health check endpoint"""
    return jsonify({
        "status": "ok",
        "service": "UDOT Road Condition API",
        "timestamp": datetime.now().isoformat()
    })

@app.route("/api/conditions")
def get_conditions():
    """Get all road conditions"""
    try:
        if not RESULTS_FILE.exists():
            return jsonify({
                "error": "Results file not found",
                "message": "Run fast_pipeline.py first to generate data"
            }), 404

        with open(RESULTS_FILE, 'r') as f:
            data = json.load(f)

        # Get file modification time
        mtime = os.path.getmtime(RESULTS_FILE)
        last_updated = datetime.fromtimestamp(mtime).isoformat()

        # Calculate statistics
        stats = {
            'total': len(data),
            'safe': sum(1 for r in data.values() if r.get('classification', {}).get('safety_level') == 'safe'),
            'caution': sum(1 for r in data.values() if r.get('classification', {}).get('safety_level') == 'caution'),
            'hazardous': sum(1 for r in data.values() if r.get('classification', {}).get('safety_level') == 'hazardous'),
            'failed': sum(1 for r in data.values() if r['status'] != 'success')
        }

        return jsonify({
            "data": data,
            "stats": stats,
            "last_updated": last_updated,
            "timestamp": datetime.now().isoformat()
        })

    except Exception as e:
        return jsonify({
            "error": str(e)
        }), 500

@app.route("/api/stats")
def get_stats():
    """Get statistics only (faster, smaller response)"""
    try:
        if not RESULTS_FILE.exists():
            return jsonify({"error": "Results file not found"}), 404

        with open(RESULTS_FILE, 'r') as f:
            data = json.load(f)

        mtime = os.path.getmtime(RESULTS_FILE)
        last_updated = datetime.fromtimestamp(mtime).isoformat()

        stats = {
            'total': len(data),
            'safe': sum(1 for r in data.values() if r.get('classification', {}).get('safety_level') == 'safe'),
            'caution': sum(1 for r in data.values() if r.get('classification', {}).get('safety_level') == 'caution'),
            'hazardous': sum(1 for r in data.values() if r.get('classification', {}).get('safety_level') == 'hazardous'),
            'failed': sum(1 for r in data.values() if r['status'] != 'success')
        }

        # Get sample hazardous cameras
        hazardous_cameras = [
            {
                'id': cam_id,
                'name': r['camera'].get('display_name', 'Unknown'),
                'lat': r['camera'].get('latitude'),
                'lon': r['camera'].get('longitude'),
                'confidence': r['classification']['confidence'],
                'condition': r['classification']['condition']
            }
            for cam_id, r in data.items()
            if r.get('classification', {}).get('safety_level') == 'hazardous'
        ][:10]  # Top 10 hazardous

        return jsonify({
            "stats": stats,
            "hazardous_cameras": hazardous_cameras,
            "last_updated": last_updated,
            "timestamp": datetime.now().isoformat()
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/camera/<camera_id>")
def get_camera(camera_id):
    """Get specific camera details"""
    try:
        if not RESULTS_FILE.exists():
            return jsonify({"error": "Results file not found"}), 404

        with open(RESULTS_FILE, 'r') as f:
            data = json.load(f)

        if camera_id not in data:
            return jsonify({"error": "Camera not found"}), 404

        return jsonify(data[camera_id])

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/route", methods=["POST"])
def plan_route():
    """
    Plan route with snow/hazard detection

    Request body (JSON):
        {
            "origin": "address or 'lon,lat'",
            "destination": "address or 'lon,lat'",
            "alternatives": 3  (optional, default 3)
        }

    Example:
        {
            "origin": "Salt Lake City, UT",
            "destination": "Park City, UT",
            "alternatives": 3
        }

    Or with coordinates:
        {
            "origin": "-111.8910,40.7608",
            "destination": "-111.4980,40.6461"
        }
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({"error": "No JSON data provided"}), 400

        origin_str = data.get('origin')
        dest_str = data.get('destination')
        alternatives = data.get('alternatives', 3)

        if not origin_str or not dest_str:
            return jsonify({
                "error": "Missing required fields",
                "message": "Both 'origin' and 'destination' are required"
            }), 400

        # Parse origin (either address or "lon,lat")
        try:
            origin_parts = origin_str.split(',')
            if len(origin_parts) == 2:
                # Try to parse as coordinates
                origin = (float(origin_parts[0]), float(origin_parts[1]))
            else:
                # Treat as address and geocode
                origin = geocode_address(origin_str)
                if not origin:
                    return jsonify({
                        "error": "Could not geocode origin",
                        "message": f"Address '{origin_str}' not found"
                    }), 400
        except ValueError:
            # Not coordinates, try geocoding
            origin = geocode_address(origin_str)
            if not origin:
                return jsonify({
                    "error": "Could not geocode origin",
                    "message": f"Address '{origin_str}' not found"
                }), 400

        # Parse destination (either address or "lon,lat")
        try:
            dest_parts = dest_str.split(',')
            if len(dest_parts) == 2:
                # Try to parse as coordinates
                destination = (float(dest_parts[0]), float(dest_parts[1]))
            else:
                # Treat as address and geocode
                destination = geocode_address(dest_str)
                if not destination:
                    return jsonify({
                        "error": "Could not geocode destination",
                        "message": f"Address '{dest_str}' not found"
                    }), 400
        except ValueError:
            # Not coordinates, try geocoding
            destination = geocode_address(dest_str)
            if not destination:
                return jsonify({
                    "error": "Could not geocode destination",
                    "message": f"Address '{dest_str}' not found"
                }), 400

        # Plan the route
        result = route_planner.plan_route(origin, destination, alternatives)

        return jsonify(result)

    except Exception as e:
        return jsonify({
            "error": "Internal server error",
            "message": str(e)
        }), 500

if __name__ == "__main__":
    # Run on all interfaces, port 5000
    # Use gunicorn in production: gunicorn -w 4 -b 0.0.0.0:5000 api_server:app
    print("=" * 70)
    print("UDOT Road Condition API Server")
    print("=" * 70)
    print(f"Results file: {RESULTS_FILE.absolute()}")
    print(f"File exists: {RESULTS_FILE.exists()}")
    print()
    print("Endpoints:")
    print("  GET  /                  - Health check")
    print("  GET  /api/conditions    - All camera data + stats")
    print("  GET  /api/stats         - Statistics only (faster)")
    print("  GET  /api/camera/<id>   - Specific camera")
    print("  POST /api/route         - Route planning with hazard detection")
    print()
    print("Starting server on http://0.0.0.0:5000")
    print("Press Ctrl+C to stop")
    print("=" * 70)

    # Development server (use gunicorn for production)
    app.run(host="0.0.0.0", port=5000, debug=False)
