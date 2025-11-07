# Utah Road Conditions API

Real-time road condition monitoring and route planning API for Utah highways using AI-powered image analysis of UDOT traffic cameras.

## Features

- **Real-time Road Condition Monitoring**: Analyzes ~900 UDOT traffic cameras using CLIP AI model
- **Hazard Detection**: Identifies snow, ice, slush, wet, and dry road conditions
- **Safety Classification**: Rates roads as safe, caution, or hazardous
- **Route Planning with Snow Detection**: NEW! Plan routes with automatic hazard detection
- **Alternative Route Suggestions**: Compares multiple routes based on safety
- **REST API**: Easy-to-use JSON API endpoints

## API Endpoints

### 1. Health Check
```
GET /
```
Returns API status and timestamp.

### 2. Get All Conditions
```
GET /api/conditions
```
Returns all camera classifications with statistics.

**Response:**
```json
{
  "data": {
    "camera_id": {
      "status": "success",
      "camera": {
        "display_name": "I-15 NB @ 300 S",
        "latitude": 40.7608,
        "longitude": -111.8910,
        "direction": "NB"
      },
      "classification": {
        "condition": "snow on road",
        "confidence": 0.87,
        "safety_level": "hazardous",
        "timestamp": "2025-11-07T10:30:00"
      }
    }
  },
  "stats": {
    "total": 900,
    "safe": 750,
    "caution": 100,
    "hazardous": 50
  }
}
```

### 3. Get Statistics Only
```
GET /api/stats
```
Returns summary statistics and top hazardous locations (faster, smaller response).

### 4. Get Specific Camera
```
GET /api/camera/<camera_id>
```
Returns details for a specific camera.

### 5. Route Planning with Hazard Detection (NEW!)
```
POST /api/route
```

Plan a route between two locations with automatic detection of snow and hazardous conditions along the way.

**Request Body:**
```json
{
  "origin": "Salt Lake City, UT",
  "destination": "Park City, UT",
  "alternatives": 3
}
```

Or use coordinates:
```json
{
  "origin": "-111.8910,40.7608",
  "destination": "-111.4980,40.6461",
  "alternatives": 2
}
```

**Parameters:**
- `origin` (required): Address string or "longitude,latitude" coordinates
- `destination` (required): Address string or "longitude,latitude" coordinates
- `alternatives` (optional): Number of alternative routes to compare (default: 3, max: 3)

**Response:**
```json
{
  "origin": {
    "longitude": -111.8910,
    "latitude": 40.7608
  },
  "destination": {
    "longitude": -111.4980,
    "latitude": 40.6461
  },
  "routes": [
    {
      "route_index": 0,
      "is_recommended": true,
      "distance_km": 35.5,
      "duration_min": 28.3,
      "safety": {
        "score": 95.0,
        "rating": "safe",
        "hazard_count": 0,
        "caution_count": 1,
        "safe_count": 5,
        "total_cameras": 6
      },
      "cameras_monitored": 6,
      "hazardous_locations": [],
      "geometry": {
        "type": "LineString",
        "coordinates": [...]
      }
    },
    {
      "route_index": 1,
      "is_recommended": false,
      "distance_km": 42.1,
      "duration_min": 32.5,
      "safety": {
        "score": 40.0,
        "rating": "hazardous",
        "hazard_count": 2,
        "caution_count": 3,
        "safe_count": 2,
        "total_cameras": 7
      },
      "cameras_monitored": 7,
      "hazardous_locations": [
        {
          "id": "cam_i80_parleys",
          "name": "I-80 EB @ Parleys Canyon MP 129",
          "latitude": 40.7344,
          "longitude": -111.7500,
          "distance_km": 0.234,
          "classification": {
            "condition": "snow on road",
            "confidence": 0.87,
            "safety_level": "hazardous"
          }
        }
      ]
    }
  ],
  "recommended_route": {
    "route_index": 0,
    "is_recommended": true,
    ...
  },
  "timestamp": "2025-11-07T10:30:00",
  "note": "Routes scored based on real-time camera data. Lower scores indicate more hazardous conditions."
}
```

**Safety Scoring:**
- **Score Range**: 0-100 (higher is safer)
- **Hazardous cameras**: -30 points each
- **Caution cameras**: -10 points each
- **Safe cameras**: +5 points each
- **Ratings**: hazardous (any snow/ice), caution (>30% caution cameras), safe, unknown

**How It Works:**
1. Geocodes addresses or parses coordinates
2. Calculates multiple routes using OSRM routing engine
3. Finds all cameras within 500m of each route
4. Checks real-time road conditions from cameras
5. Scores each route based on safety
6. Recommends the safest route

**Example cURL Request:**
```bash
curl -X POST http://your-server:5000/api/route \
  -H "Content-Type: application/json" \
  -d '{
    "origin": "Salt Lake City, UT",
    "destination": "Park City, UT",
    "alternatives": 3
  }'
```

**Example JavaScript (Fetch):**
```javascript
fetch('http://your-server:5000/api/route', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    origin: 'Salt Lake City, UT',
    destination: 'Park City, UT',
    alternatives: 3
  })
})
.then(response => response.json())
.then(data => {
  console.log('Recommended route:', data.recommended_route);
  console.log('Safety score:', data.recommended_route.safety.score);
});
```

## Safety Levels

- 🟢 **Safe**: Clear/dry roads or clear with snow on sides only
- 🟡 **Caution**: Wet road surfaces
- 🔴 **Hazardous**: Snow, ice, or slush detected on road
- ⚪ **Unknown**: Unable to determine conditions

## Installation

### Requirements
```bash
pip install -r requirements.txt
```

### Dependencies
- transformers (CLIP model)
- torch (PyTorch)
- pillow (image processing)
- requests
- flask + flask-cors
- gunicorn (production server)
- google-api-python-client (Drive backup)

## Running the Server

### Development
```bash
python3 api_server.py
```

### Production (with Gunicorn)
```bash
gunicorn -w 4 -b 0.0.0.0:5000 api_server:app
```

### With systemd (VPS deployment)
See `systemd/` directory for service configurations.

## Data Pipeline

1. **KML Camera Client**: Fetches camera list from UDOT
2. **Image Downloader**: Downloads camera images (parallel, 4 workers)
3. **Road Classifier**: CLIP-based AI classification
4. **Results Cache**: Saves to `data/fast_classified/classification_results.json`
5. **API Server**: Serves results via REST API
6. **Route Planner**: Analyzes routes using cached results

### Update Camera Data
```bash
python3 fast_pipeline.py
```
Processes all ~900 cameras in ~12-18 minutes.

## Route Planning Technical Details

### Routing Engine
- Primary: OSRM (Open Source Routing Machine)
- Fallback: Simple straight-line approximation
- Supports multiple OSRM server instances

### Camera Matching
- Buffer distance: 500m from route path
- Uses haversine distance for accuracy
- Point-to-line segment distance calculation

### Geocoding
- Service: Nominatim (OpenStreetMap)
- Fallback: Direct coordinate input
- Format: "longitude,latitude"

## Architecture

```
┌─────────────────┐
│  UDOT Cameras   │
│   (KML Feed)    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐      ┌──────────────┐
│ Fast Pipeline   │─────►│ CLIP Model   │
│ (Image Proc)    │      │ (AI Classify)│
└────────┬────────┘      └──────────────┘
         │
         ▼
┌─────────────────┐
│ Results JSON    │
│   (Cache)       │
└────────┬────────┘
         │
    ┌────┴────┐
    │         │
    ▼         ▼
┌─────────┐ ┌──────────────┐
│ API     │ │ Route        │
│ Server  │ │ Planner      │
└────┬────┘ └──────┬───────┘
     │             │
     ▼             ▼
┌─────────────────────────┐
│   REST API Clients      │
│ (Frontend/Mobile/etc)   │
└─────────────────────────┘
```

## Project Structure

```
utah-road-conditions-api/
├── api_server.py              # Flask REST API server
├── route_planner.py           # Route planning with hazard detection
├── fast_pipeline.py           # Image processing pipeline
├── fast_road_classifier.py    # CLIP-based classifier
├── kml_camera_client.py       # UDOT camera data client
├── gdrive_uploader.py         # Google Drive backup
├── requirements.txt           # Python dependencies
├── systemd/                   # System service configs
│   ├── udot-api.service
│   ├── udot-detection.service
│   └── udot-detection.timer
└── data/
    ├── kml_cameras/           # Downloaded images
    └── fast_classified/       # Classification results
        └── classification_results.json
```

## Use Cases

### 1. Road Condition Monitoring Dashboard
Display current conditions on a map using `/api/conditions` and `/api/stats`.

### 2. Route Planning Application
Build a navigation app that recommends safer routes using `/api/route`.

### 3. Winter Travel Advisory System
Alert users about hazardous conditions on their planned routes.

### 4. Fleet Management
Help trucking/delivery companies choose safer routes in winter.

### 5. Emergency Services
Provide first responders with real-time road condition data.

## Performance

- **Camera Processing**: ~12-18 minutes for 900 cameras
- **API Response Time**: <100ms for cached data
- **Route Planning**: 2-5 seconds (depends on routing service)
- **Memory Usage**: ~1.5 GB during processing
- **Update Frequency**: Every 16 minutes (configurable)

## Camera Coverage

- Major interstates: I-15, I-80, I-70, I-84
- US highways: US-6, US-89, US-189, US-191
- State routes: SR-9, SR-14, SR-92, etc.
- Mountain passes and canyons
- Urban corridors (Salt Lake, Provo, Ogden)

## Limitations

- Route planning limited to Utah (UDOT cameras only)
- OSRM public servers may have rate limits
- Geocoding requires internet connection
- Camera coverage varies by region
- Real-time conditions depend on camera availability

## Future Enhancements

- [ ] Historical route safety analysis
- [ ] Weather forecast integration
- [ ] Real-time traffic integration
- [ ] Mobile push notifications
- [ ] Machine learning route optimization
- [ ] Multi-state support
- [ ] Self-hosted OSRM instance

## Contributing

This is a production system for Utah road monitoring. For changes:
1. Test thoroughly with sample data
2. Ensure backward compatibility
3. Update documentation
4. Test on VPS before deploying

## License

See project license file.

## Support

For issues or questions about the API, check the system logs or contact the maintainer.

## Acknowledgments

- UDOT for traffic camera data
- OpenAI for CLIP model
- OSRM project for routing
- OpenStreetMap for geocoding
