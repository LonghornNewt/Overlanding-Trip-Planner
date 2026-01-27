from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import math

app = FastAPI(title="Overlanding Trip Planner API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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

class TripPlan(BaseModel):
    total_distance_miles: float
    total_drive_time_hours: float
    segments: List[RouteSegment]
    nearby_campsites: List[Campsite]

def haversine_distance(lat1, lon1, lat2, lon2):
    """Calculate distance in miles between two coordinates"""
    R = 3959  # Earth radius in miles
    lat1_rad, lat2_rad = math.radians(lat1), math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)
    a = math.sin(delta_lat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R * c

def get_mock_campsites(center_lat, center_lon, radius_miles=50):
    """Mock campsite data - will be replaced with real API calls"""
    mock_data = [
        Campsite(
            id="iov_001", name="Hidden Valley Dispersed",
            lat=center_lat+0.15, lon=center_lon-0.2, type="dispersed",
            amenities=["fire_ring", "flat_ground"], elevation=5200,
            rating=4.5, cell_service="weak", difficulty="moderate",
            source="iOverlander"
        ),
        Campsite(
            id="rec_001", name="Pine Creek Campground",
            lat=center_lat-0.1, lon=center_lon+0.15, type="campground",
            amenities=["restrooms", "water", "picnic_table", "fire_ring"],
            elevation=4800, rating=4.2, cell_service="good",
            difficulty="easy", source="recreation_gov"
        ),
        Campsite(
            id="free_001", name="BLM Road 4520 Spot",
            lat=center_lat+0.08, lon=center_lon-0.12, type="dispersed",
            amenities=["fire_ring"], elevation=6100, rating=4.8,
            cell_service="none", difficulty="moderate",
            source="freecampsites"
        ),
        Campsite(
            id="rv_001", name="Mountain View RV Park",
            lat=center_lat-0.05, lon=center_lon+0.08, type="rv_park",
            amenities=["full_hookup", "wifi", "showers", "laundry"],
            elevation=4500, rating=3.9, cell_service="excellent",
            source="user"
        ),
    ]
    for site in mock_data:
        site.distance_from_route = haversine_distance(center_lat, center_lon, site.lat, site.lon)
    return [s for s in mock_data if s.distance_from_route <= radius_miles]

@app.get("/")
async def root():
    return {"message": "Overlanding Trip Planner API", "version": "1.0.0"}

@app.get("/api/health")
async def health_check():
    return {"status": "healthy", "services": {"database": "mock", "external_apis": "ready"}}

@app.post("/api/trip/plan", response_model=TripPlan)
async def plan_trip(request: TripRequest):
    """Plan a multi-day overlanding trip with campsite suggestions"""
    total_distance = haversine_distance(
        request.start.lat, request.start.lon,
        request.destination.lat, request.destination.lon
    )
    avg_speed = 50  # mph for overlanding
    total_time = total_distance / avg_speed
    days_needed = max(1, math.ceil(total_time / request.daily_drive_hours))
    
    segments = []
    for day in range(1, days_needed + 1):
        progress = day / days_needed
        prev_progress = (day - 1) / days_needed
        
        segment_start = Coordinates(
            lat=request.start.lat + (request.destination.lat - request.start.lat) * prev_progress,
            lon=request.start.lon + (request.destination.lon - request.start.lon) * prev_progress
        )
        segment_end = Coordinates(
            lat=request.start.lat + (request.destination.lat - request.start.lat) * progress,
            lon=request.start.lon + (request.destination.lon - request.start.lon) * progress
        )
        
        nearby = get_mock_campsites(segment_end.lat, segment_end.lon, request.max_detour_miles)
        suggested = nearby[0] if nearby else None
        
        segments.append(RouteSegment(
            day=day,
            start_point=segment_start,
            end_point=segment_end,
            distance_miles=round(total_distance / days_needed, 1),
            drive_time_hours=round(total_time / days_needed, 1),
            suggested_campsite=suggested
        ))
    
    mid_lat = (request.start.lat + request.destination.lat) / 2
    mid_lon = (request.start.lon + request.destination.lon) / 2
    all_campsites = get_mock_campsites(mid_lat, mid_lon, total_distance / 2)
    
    return TripPlan(
        total_distance_miles=round(total_distance, 1),
        total_drive_time_hours=round(total_time, 1),
        segments=segments,
        nearby_campsites=all_campsites
    )

@app.get("/api/campsites/search", response_model=List[Campsite])
async def search_campsites(
    lat: float = Query(..., description="Center latitude"),
    lon: float = Query(..., description="Center longitude"),
    radius: float = Query(50, description="Search radius in miles"),
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

@app.get("/api/route/optimize")
async def optimize_route(
    start_lat: float, start_lon: float,
    end_lat: float, end_lon: float,
    include_campsites: bool = True
):
    """Optimize route with best campsite waypoints"""
    direct_distance = haversine_distance(start_lat, start_lon, end_lat, end_lon)
    waypoints = []
    
    if include_campsites:
        mid_lat = (start_lat + end_lat) / 2
        mid_lon = (start_lon + end_lon) / 2
        campsites = get_mock_campsites(mid_lat, mid_lon, 30)
        accessible = [c for c in campsites if c.gx460_accessible and c.rating]
        if accessible:
            best = max(accessible, key=lambda x: x.rating or 0)
            waypoints.append({
                "campsite": best,
                "added_distance_miles": best.distance_from_route * 2
            })
    
    return {
        "direct_distance_miles": round(direct_distance, 1),
        "optimized_waypoints": waypoints,
        "total_with_waypoints": round(
            direct_distance + sum(w["added_distance_miles"] for w in waypoints), 1
        )
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)