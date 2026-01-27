from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import math
import httpx

app = FastAPI(title="Overlanding Trip Planner API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# OSRM public demo server (for production, consider self-hosting)
OSRM_BASE_URL = "https://router.project-osrm.org"

class Coordinates(BaseModel):
    lat: float
    lon: float

class TripRequest(BaseModel):
    start: Coordinates
    destination: Coordinates
    max_detour_miles: float = 25.0
    campsite_types: List[str] = ["dispersed", "campground"]
    daily_drive_hours: float = 8.0

class Campsite(BaseModel):
    id: str
    name: str
    lat: float
    lon: float
    type: str
    amenities: List[str] = []
    distance_from_route: float = 0.0
    elevation: Optional[int] = None
    rating: Optional[float] = None
    cell_service: Optional[str] = None
    difficulty: Optional[str] = None
    gx460_accessible: bool = True
    source: str = "mock"

class RouteSegment(BaseModel):
    day: int
    start_point: Coordinates
    end_point: Coordinates
    distance_miles: float
    drive_time_hours: float
    suggested_campsite: Optional[Campsite] = None
    route_geometry: Optional[List[List[float]]] = None  # [[lon, lat], ...] for this segment

class Direction(BaseModel):
    instruction: str
    distance_miles: float
    duration_minutes: float
    maneuver_type: str
    maneuver_modifier: str
    ref: str  # Highway number

class TripPlan(BaseModel):
    total_distance_miles: float
    total_drive_time_hours: float
    segments: List[RouteSegment]
    nearby_campsites: List[Campsite]
    route_geometry: List[List[float]] = []  # Full route [[lon, lat], ...]
    directions: List[Direction] = []  # Turn-by-turn directions

def haversine_distance(lat1, lon1, lat2, lon2):
    """Calculate distance in miles between two coordinates"""
    R = 3959  # Earth radius in miles
    lat1_rad, lat2_rad = math.radians(lat1), math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)
    a = math.sin(delta_lat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R * c

async def get_osrm_route(start_lon: float, start_lat: float, end_lon: float, end_lat: float):
    """Get driving route from OSRM"""
    url = f"{OSRM_BASE_URL}/route/v1/driving/{start_lon},{start_lat};{end_lon},{end_lat}"
    params = {
        "overview": "full",
        "geometries": "geojson",
        "steps": "true",
        "annotations": "true"
    }
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, params=params, timeout=10.0)
            response.raise_for_status()
            data = response.json()
            
            if data.get("code") == "Ok" and data.get("routes"):
                route = data["routes"][0]
                
                # Extract turn-by-turn directions
                directions = []
                for leg in route.get("legs", []):
                    for step in leg.get("steps", []):
                        maneuver = step.get("maneuver", {})
                        direction = {
                            "instruction": step.get("name", ""),
                            "distance_miles": round(step.get("distance", 0) * 0.000621371, 1),
                            "duration_minutes": round(step.get("duration", 0) / 60, 1),
                            "maneuver_type": maneuver.get("type", ""),
                            "maneuver_modifier": maneuver.get("modifier", ""),
                            "ref": step.get("ref", "")  # Highway number like "I-35"
                        }
                        # Only include meaningful steps
                        if direction["distance_miles"] > 0.1:
                            directions.append(direction)
                
                return {
                    "distance_miles": route["distance"] * 0.000621371,  # meters to miles
                    "duration_hours": route["duration"] / 3600,  # seconds to hours
                    "geometry": route["geometry"]["coordinates"],  # [[lon, lat], ...]
                    "directions": directions
                }
        except Exception as e:
            print(f"OSRM error: {e}")
    
    return None

def decode_polyline_to_points(geometry: List[List[float]], num_points: int = 10) -> List[List[float]]:
    """Sample points along the route geometry"""
    if not geometry or len(geometry) < 2:
        return []
    
    step = max(1, len(geometry) // num_points)
    return geometry[::step]

def get_mock_campsites(center_lat, center_lon, radius_miles, route_geometry=None):
    """Mock campsite data - will be replaced with real API calls"""
    
    # If we have route geometry, generate campsites near the route
    if route_geometry and len(route_geometry) > 0:
        # Sample points along route to place campsites near
        sample_points = decode_polyline_to_points(route_geometry, 8)
    else:
        sample_points = [[center_lon, center_lat]]
    
    mock_data = []
    campsite_templates = [
        {
            "name": "Hidden Valley Dispersed",
            "type": "dispersed",
            "amenities": ["fire_ring", "flat_ground"],
            "elevation": 5200,
            "rating": 4.5,
            "cell_service": "weak",
            "difficulty": "moderate",
            "source": "iOverlander"
        },
        {
            "name": "Pine Creek Campground",
            "type": "campground",
            "amenities": ["restrooms", "water", "picnic_table", "fire_ring"],
            "elevation": 4800,
            "rating": 4.2,
            "cell_service": "good",
            "difficulty": "easy",
            "source": "recreation_gov"
        },
        {
            "name": "BLM Road 4520 Spot",
            "type": "dispersed",
            "amenities": ["fire_ring"],
            "elevation": 6100,
            "rating": 4.8,
            "cell_service": "none",
            "difficulty": "moderate",
            "source": "freecampsites"
        },
        {
            "name": "Mountain View RV Park",
            "type": "rv_park",
            "amenities": ["full_hookup", "wifi", "showers", "laundry"],
            "elevation": 4500,
            "rating": 3.9,
            "cell_service": "excellent",
            "difficulty": "easy",
            "source": "user"
        },
        {
            "name": "Red Rock Dispersed Camp",
            "type": "dispersed",
            "amenities": ["fire_ring", "shade"],
            "elevation": 5800,
            "rating": 4.6,
            "cell_service": "weak",
            "difficulty": "difficult",
            "source": "iOverlander"
        },
        {
            "name": "Riverside State Park",
            "type": "campground",
            "amenities": ["restrooms", "water", "showers", "picnic_table"],
            "elevation": 4200,
            "rating": 4.0,
            "cell_service": "good",
            "difficulty": "easy",
            "source": "recreation_gov"
        }
    ]
    
    # Generate campsites near sample points along route
    for i, point in enumerate(sample_points):
        template = campsite_templates[i % len(campsite_templates)]
        # Offset slightly from route
        lat_offset = (i % 3 - 1) * 0.08
        lon_offset = (i % 2) * 0.1
        
        site = Campsite(
            id=f"site_{i:03d}",
            name=f"{template['name']} #{i+1}",
            lat=point[1] + lat_offset,  # geometry is [lon, lat]
            lon=point[0] + lon_offset,
            type=template["type"],
            amenities=template["amenities"],
            elevation=template["elevation"] + (i * 100),
            rating=template["rating"],
            cell_service=template["cell_service"],
            difficulty=template["difficulty"],
            gx460_accessible=template["difficulty"] != "difficult",
            source=template["source"]
        )
        mock_data.append(site)
    
    # Calculate distance from route center for each site
    for site in mock_data:
        site.distance_from_route = haversine_distance(center_lat, center_lon, site.lat, site.lon)
    
    return [s for s in mock_data if s.distance_from_route <= radius_miles]

@app.get("/api/geocode")
async def geocode(q: str = Query(..., description="City name or address to geocode")):
    """Convert a city name or address to coordinates using Nominatim"""
    url = "https://nominatim.openstreetmap.org/search"
    params = {
        "q": q,
        "format": "json",
        "limit": 5,
        "countrycodes": "us"  # Limit to US for overlanding trips
    }
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                url, 
                params=params, 
                headers={"User-Agent": "OverlandingTripPlanner/1.0"},
                timeout=10.0
            )
            response.raise_for_status()
            results = response.json()
            
            if results:
                return [
                    {
                        "name": r.get("display_name"),
                        "lat": float(r.get("lat")),
                        "lon": float(r.get("lon"))
                    }
                    for r in results
                ]
            return []
        except Exception as e:
            print(f"Geocoding error: {e}")
            raise HTTPException(status_code=500, detail="Geocoding failed")

@app.get("/")
async def root():
    return {"message": "Overlanding Trip Planner API", "version": "1.0.0"}

@app.get("/api/health")
async def health_check():
    return {"status": "healthy", "services": {"database": "mock", "external_apis": "ready", "osrm": "connected"}}

@app.post("/api/trip/plan", response_model=TripPlan)
async def plan_trip(request: TripRequest):
    """Plan a multi-day overlanding trip with campsite suggestions and real routing"""
    
    # Get actual driving route from OSRM
    route_data = await get_osrm_route(
        request.start.lon, request.start.lat,
        request.destination.lon, request.destination.lat
    )
    
    if route_data:
        total_distance = route_data["distance_miles"]
        total_time = route_data["duration_hours"]
        full_geometry = route_data["geometry"]
        directions = route_data.get("directions", [])
    else:
        # Fallback to straight-line calculation
        total_distance = haversine_distance(
            request.start.lat, request.start.lon,
            request.destination.lat, request.destination.lon
        )
        avg_speed = 45  # mph for overlanding
        total_time = total_distance / avg_speed
        full_geometry = [
            [request.start.lon, request.start.lat],
            [request.destination.lon, request.destination.lat]
        ]
        directions = []
    
    # Calculate days based on user's preferred daily drive hours
    days_needed = max(1, math.ceil(total_time / request.daily_drive_hours))
    
    # Calculate what fraction of the route to cover each day
    hours_per_day = total_time / days_needed
    miles_per_day = total_distance / days_needed
    
    # Build segments with campsites at logical stopping points
    segments = []
    all_segment_campsites = []
    
    for day in range(1, days_needed + 1):
        # Calculate progress along route (0.0 to 1.0)
        day_end_progress = day / days_needed
        day_start_progress = (day - 1) / days_needed
        
        # Find geometry indices for this segment
        total_points = len(full_geometry)
        start_idx = int(day_start_progress * (total_points - 1))
        end_idx = int(day_end_progress * (total_points - 1))
        
        segment_geometry = full_geometry[start_idx:end_idx + 1]
        
        if len(segment_geometry) >= 1:
            segment_start = Coordinates(
                lat=full_geometry[start_idx][1],
                lon=full_geometry[start_idx][0]
            )
            segment_end = Coordinates(
                lat=full_geometry[end_idx][1],
                lon=full_geometry[end_idx][0]
            )
        else:
            # Fallback
            segment_start = Coordinates(
                lat=request.start.lat + (request.destination.lat - request.start.lat) * day_start_progress,
                lon=request.start.lon + (request.destination.lon - request.start.lon) * day_start_progress
            )
            segment_end = Coordinates(
                lat=request.start.lat + (request.destination.lat - request.start.lat) * day_end_progress,
                lon=request.start.lon + (request.destination.lon - request.start.lon) * day_end_progress
            )
            segment_geometry = [[segment_start.lon, segment_start.lat], [segment_end.lon, segment_end.lat]]
        
        # Find campsites near the END of each day's drive (where you'd want to stop)
        nearby = get_mock_campsites(
            segment_end.lat, 
            segment_end.lon, 
            request.max_detour_miles, 
            segment_geometry
        )
        
        # Pick the best campsite for this stop (highest rated, GX460 accessible)
        suggested = None
        if nearby:
            # Sort by: GX460 accessible first, then by rating
            accessible_sites = sorted(
                [s for s in nearby if s.gx460_accessible],
                key=lambda x: x.rating or 0,
                reverse=True
            )
            if accessible_sites:
                suggested = accessible_sites[0]
            else:
                suggested = nearby[0]
        
        # Calculate cumulative distance and time at end of this day
        cumulative_miles = round(miles_per_day * day, 1)
        cumulative_hours = round(hours_per_day * day, 1)
        
        segments.append(RouteSegment(
            day=day,
            start_point=segment_start,
            end_point=segment_end,
            distance_miles=round(miles_per_day, 1),
            drive_time_hours=round(hours_per_day, 1),
            suggested_campsite=suggested,
            route_geometry=segment_geometry
        ))
        
        # Collect all nearby campsites for this segment
        all_segment_campsites.extend(nearby)
    
    # Remove duplicate campsites (same id)
    seen_ids = set()
    unique_campsites = []
    for site in all_segment_campsites:
        if site.id not in seen_ids:
            seen_ids.add(site.id)
            unique_campsites.append(site)
    
    return TripPlan(
        total_distance_miles=round(total_distance, 1),
        total_drive_time_hours=round(total_time, 1),
        segments=segments,
        nearby_campsites=unique_campsites,
        route_geometry=full_geometry,
        directions=[Direction(**d) for d in directions]
    )

@app.get("/api/campsites/search", response_model=List[Campsite])
async def search_campsites(
    lat: float = Query(..., description="Center latitude"),
    lon: float = Query(..., description="Center longitude"),
    radius: float = Query(25, description="Search radius in miles"),
    type: Optional[str] = Query(None, description="Filter: dispersed, campground, rv_park"),
    min_rating: Optional[float] = Query(None, description="Minimum rating")
):
    """Search for campsites near a location"""
    campsites = get_mock_campsites(lat, lon, radius)
    
    if type:
        campsites = [c for c in campsites if c.type == type]
    
    if min_rating:
        campsites = [c for c in campsites if c.rating and c.rating >= min_rating]
    
    return sorted(campsites, key=lambda x: x.distance_from_route)

@app.get("/api/campsites/{campsite_id}", response_model=Campsite)
async def get_campsite_details(campsite_id: str):
    """Get details for a specific campsite"""
    all_campsites = get_mock_campsites(35.0, -105.0, 100)
    for site in all_campsites:
        if site.id == campsite_id:
            return site
    raise HTTPException(status_code=404, detail="Campsite not found")

@app.get("/api/route/preview")
async def preview_route(
    start_lat: float, start_lon: float,
    end_lat: float, end_lon: float
):
    """Get just the route geometry for preview"""
    route_data = await get_osrm_route(start_lon, start_lat, end_lon, end_lat)
    
    if route_data:
        return {
            "distance_miles": round(route_data["distance_miles"], 1),
            "duration_hours": round(route_data["duration_hours"], 1),
            "geometry": route_data["geometry"]
        }
    
    # Fallback
    return {
        "distance_miles": round(haversine_distance(start_lat, start_lon, end_lat, end_lon), 1),
        "duration_hours": None,
        "geometry": [[start_lon, start_lat], [end_lon, end_lat]]
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
