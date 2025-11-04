#!/usr/bin/env python3
"""
Lightweight Flask API server for VPS
Serves classification results JSON with CORS headers
"""

from flask import Flask, jsonify, send_file
from flask_cors import CORS
from pathlib import Path
import json
from datetime import datetime
import os

app = Flask(__name__)

# Enable CORS for all routes (allows Vercel to fetch)
CORS(app)

# Path to results file
RESULTS_FILE = Path("data/fast_classified/classification_results.json")

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
    print("  GET /                  - Health check")
    print("  GET /api/conditions    - All camera data + stats")
    print("  GET /api/stats         - Statistics only (faster)")
    print("  GET /api/camera/<id>   - Specific camera")
    print()
    print("Starting server on http://0.0.0.0:5000")
    print("Press Ctrl+C to stop")
    print("=" * 70)

    # Development server (use gunicorn for production)
    app.run(host="0.0.0.0", port=5000, debug=False)
