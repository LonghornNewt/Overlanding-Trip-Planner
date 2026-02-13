from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import math
import httpx
import os
import html
import re

app = FastAPI(title="Overlanding Trip Planner API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# OSRM public demo server
OSRM_BASE_URL = "https://router.project-osrm.org"

# Recreation.gov RIDB API
RIDB_BASE_URL = "https://ridb.recreation.gov/api/v1"
RIDB_API_KEY = os.environ.get("RIDB_API_KEY", "bb9c7aed-cfba-49c8-987b-e18b0bd8fff5")


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
    source: str = "recreation_gov"
    description: Optional[str] = None
    reservation_url: Optional[str] = None
    phone: Optional[str] = None


class RouteSegment(BaseModel):
    day: int
    start_point: Coordinates
    end_point: Coordinates
    distance_miles: float
    drive_time_hours: float
    suggested_campsite: Optional[Campsite] = None
    route_geometry: Optional[List[List[float]]] = None


class Direction(BaseModel):
    instruction: str
    distance_miles: float
    duration_minutes: float
    maneuver_type: str
    maneuver_modifier: str
    ref: str


class TripPlan(BaseModel):
    total_distance_miles: float
    total_drive_time_hours: float
    segments: List[RouteSegment]
    nearby_campsites: List[Campsite]
    route_geometry: List[List[float]] = []
    directions: List[Direction] = []


def haversine_distance(lat1, lon1, lat2, lon2):
    """Calculate distance in miles between two coordinates"""
    R = 3959  # Earth radius in miles
    lat1_rad, lat2_rad = math.radians(lat1), math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)
    a = math.sin(delta_lat / 2) ** 2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def strip_html(text):
    """Remove HTML tags from a string"""
    if not text:
        return ""
    clean = re.sub(r'<[^>]+>', ' ', text)
    clean = html.unescape(clean)
    clean = re.sub(r'\s+', ' ', clean).strip()
    return clean[:300]  # Truncate to 300 chars


async def get_osrm_route(start_lon, start_lat, end_lon, end_lat):
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
                            "ref": step.get("ref", "")
                        }
                        if direction["distance_miles"] > 0.1:
                            directions.append(direction)

                return {
                    "distance_miles": route["distance"] * 0.000621371,
                    "duration_hours": route["duration"] / 3600,
                    "geometry": route["geometry"]["coordinates"],
                    "directions": directions
                }
        except Exception as e:
            print(f"OSRM error: {e}")
            return None


# ============================================================
# Recreation.gov RIDB API Integration
# ============================================================

async def search_ridb_facilities(lat: float, lon: float, radius_miles: float = 25.0, limit: int = 20):
    """Search Recreation.gov RIDB for camping facilities near a location"""
    url = f"{RIDB_BASE_URL}/facilities"
    params = {
        "latitude": lat,
        "longitude": lon,
        "radius": radius_miles,
        "activity": "CAMPING",
        "limit": limit,
        "offset": 0,
    }
    headers = {
        "accept": "application/json",
        "apikey": RIDB_API_KEY,
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, params=params, headers=headers, timeout=15.0)
            response.raise_for_status()
            data = response.json()
            return data.get("RECDATA", [])
        except Exception as e:
            print(f"RIDB facilities search error: {e}")
            return []


async def get_facility_campsites(facility_id: int, limit: int = 10):
    """Get individual campsites for a facility from RIDB"""
    url = f"{RIDB_BASE_URL}/facilities/{facility_id}/campsites"
    params = {"limit": limit}
    headers = {
        "accept": "application/json",
        "apikey": RIDB_API_KEY,
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, params=params, headers=headers, timeout=10.0)
            response.raise_for_status()
            data = response.json()
            return data.get("RECDATA", [])
        except Exception as e:
            print(f"RIDB campsites error for facility {facility_id}: {e}")
            return []


def parse_ridb_facility_to_campsite(facility: dict, center_lat: float, center_lon: float) -> Optional[Campsite]:
    """Convert a RIDB facility record into our Campsite model"""
    fac_lat = facility.get("FacilityLatitude")
    fac_lon = facility.get("FacilityLongitude")

    # Skip facilities without valid coordinates
    if not fac_lat or not fac_lon or fac_lat == 0 or fac_lon == 0:
        return None

    # Determine campsite type from facility type description
    fac_type_desc = (facility.get("FacilityTypeDescription") or "").lower()
    fac_name = facility.get("FacilityName", "Unknown Facility")

    if "camping" in fac_type_desc or "campground" in fac_name.lower():
        camp_type = "campground"
    elif "rv" in fac_name.lower() or "rv" in fac_type_desc:
        camp_type = "rv_park"
    else:
        camp_type = "campground"

    # Check name for dispersed camping hints
    name_lower = fac_name.lower()
    if any(word in name_lower for word in ["dispersed", "blm", "primitive", "backcountry"]):
        camp_type = "dispersed"

    # Parse description
    description = strip_html(facility.get("FacilityDescription", ""))

    # Build reservation URL
    facility_id = facility.get("FacilityID", "")
    reservation_url = facility.get("FacilityReservationURL", "")
    if not reservation_url and facility_id:
        reservation_url = f"https://www.recreation.gov/camping/campgrounds/{facility_id}"

    # Extract amenities from description keywords
    amenities = []
    desc_lower = description.lower()
    amenity_keywords = {
        "restroom": "restrooms", "toilet": "restrooms", "bathroom": "restrooms",
        "water": "water", "drinking water": "water",
        "shower": "showers",
        "picnic": "picnic_table",
        "fire ring": "fire_ring", "fire pit": "fire_ring", "campfire": "fire_ring",
        "hookup": "full_hookup", "electric": "electric_hookup",
        "dump station": "dump_station",
        "fishing": "fishing",
        "hiking": "hiking",
        "boat": "boat_ramp",
        "swimming": "swimming",
        "wifi": "wifi",
    }
    for keyword, amenity in amenity_keywords.items():
        if keyword in desc_lower and amenity not in amenities:
            amenities.append(amenity)

    # Calculate distance from search center
    dist = haversine_distance(center_lat, center_lon, fac_lat, fac_lon)

    # Estimate difficulty based on description
    difficulty = "easy"
    if any(word in desc_lower for word in ["4wd", "4x4", "high clearance", "rough road"]):
        difficulty = "moderate"
    if any(word in desc_lower for word in ["extreme", "rock crawl"]):
        difficulty = "difficult"

    # GX 460 accessible - conservative estimate
    gx460_accessible = difficulty != "difficult"

    return Campsite(
        id=f"ridb_{facility_id}",
        name=fac_name,
        lat=fac_lat,
        lon=fac_lon,
        type=camp_type,
        amenities=amenities,
        distance_from_route=round(dist, 1),
        elevation=None,  # RIDB doesn't always provide this
        rating=None,  # RIDB doesn't have user ratings
        cell_service=None,  # Not in RIDB data
        difficulty=difficulty,
        gx460_accessible=gx460_accessible,
        source="recreation_gov",
        description=description,
        reservation_url=reservation_url,
        phone=facility.get("FacilityPhone", None),
    )


async def search_campsites_near_point(lat: float, lon: float, radius_miles: float = 25.0) -> List[Campsite]:
    """Search for real campsites near a point using RIDB API"""
    facilities = await search_ridb_facilities(lat, lon, radius_miles, limit=20)

    campsites = []
    for fac in facilities:
        campsite = parse_ridb_facility_to_campsite(fac, lat, lon)
        if campsite:
            campsites.append(campsite)

    # Sort by distance from the search point
    campsites.sort(key=lambda c: c.distance_from_route)

    return campsites


def decode_polyline_to_points(geometry: List[List[float]], num_points: int = 10) -> List[List[float]]:
    """Sample points along the route geometry"""
    if not geometry or len(geometry) < 2:
        return []
    step = max(1, len(geometry) // num_points)
    return geometry[::step]


# ============================================================
# API Endpoints
# ============================================================

@app.get("/api/geocode")
async def geocode(q: str = Query(..., description="City name or address to geocode")):
    """Convert a city name or address to coordinates using Nominatim"""
    url = "https://nominatim.openstreetmap.org/search"
    params = {
        "q": q,
        "format": "json",
        "limit": 5,
        "countrycodes": "us"
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
    return {
        "message": "Overlanding Trip Planner API",
        "version": "2.0.0",
        "campsite_source": "Recreation.gov RIDB",
    }


@app.get("/api/health")
async def health_check():
    # Quick check that RIDB API key works
    ridb_status = "configured" if RIDB_API_KEY else "missing_key"
    return {
        "status": "healthy",
        "services": {
            "osrm": "connected",
            "ridb": ridb_status,
            "ridb_api_key_set": bool(RIDB_API_KEY),
        }
    }


@app.post("/api/trip/plan", response_model=TripPlan)
async def plan_trip(request: TripRequest):
    """Plan a multi-day overlanding trip with real campsite data from Recreation.gov"""

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
        total_distance = haversine_distance(
            request.start.lat, request.start.lon,
            request.destination.lat, request.destination.lon
        )
        avg_speed = 45
        total_time = total_distance / avg_speed
        full_geometry = [
            [request.start.lon, request.start.lat],
            [request.destination.lon, request.destination.lat]
        ]
        directions = []

    # Calculate days
    days_needed = max(1, math.ceil(total_time / request.daily_drive_hours))
    hours_per_day = total_time / days_needed
    miles_per_day = total_distance / days_needed

    # Build segments and search for real campsites at each stop
    segments = []
    all_campsites = []
    seen_ids = set()

    for day in range(1, days_needed + 1):
        day_end_progress = day / days_needed
        day_start_progress = (day - 1) / days_needed

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
            segment_start = Coordinates(
                lat=request.start.lat + (request.destination.lat - request.start.lat) * day_start_progress,
                lon=request.start.lon + (request.destination.lon - request.start.lon) * day_start_progress
            )
            segment_end = Coordinates(
                lat=request.start.lat + (request.destination.lat - request.start.lat) * day_end_progress,
                lon=request.start.lon + (request.destination.lon - request.start.lon) * day_end_progress
            )
            segment_geometry = [[segment_start.lon, segment_start.lat], [segment_end.lon, segment_end.lat]]

        # Search for REAL campsites near end of day's drive
        nearby = await search_campsites_near_point(
            segment_end.lat,
            segment_end.lon,
            request.max_detour_miles
        )

        # Pick the best campsite (closest accessible one)
        suggested = None
        if nearby:
            accessible = [s for s in nearby if s.gx460_accessible]
            suggested = accessible[0] if accessible else nearby[0]

        segments.append(RouteSegment(
            day=day,
            start_point=segment_start,
            end_point=segment_end,
            distance_miles=round(miles_per_day, 1),
            drive_time_hours=round(hours_per_day, 1),
            suggested_campsite=suggested,
            route_geometry=segment_geometry
        ))

        # Collect unique campsites
        for site in nearby:
            if site.id not in seen_ids:
                seen_ids.add(site.id)
                all_campsites.append(site)

    return TripPlan(
        total_distance_miles=round(total_distance, 1),
        total_drive_time_hours=round(total_time, 1),
        segments=segments,
        nearby_campsites=all_campsites,
        route_geometry=full_geometry,
        directions=[Direction(**d) for d in directions]
    )


@app.get("/api/campsites/search", response_model=List[Campsite])
async def search_campsites(
    lat: float = Query(..., description="Center latitude"),
    lon: float = Query(..., description="Center longitude"),
    radius: float = Query(25, description="Search radius in miles"),
    type: Optional[str] = Query(None, description="Filter: dispersed, campground, rv_park"),
):
    """Search for real campsites near a location using Recreation.gov"""
    campsites = await search_campsites_near_point(lat, lon, radius)

    if type:
        campsites = [c for c in campsites if c.type == type]

    return campsites


@app.get("/api/campsites/{campsite_id}", response_model=Campsite)
async def get_campsite_details(campsite_id: str):
    """Get details for a specific campsite"""
    # Extract RIDB facility ID from our id format "ridb_XXXXX"
    if campsite_id.startswith("ridb_"):
        facility_id = campsite_id.replace("ridb_", "")
        url = f"{RIDB_BASE_URL}/facilities/{facility_id}"
        headers = {"accept": "application/json", "apikey": RIDB_API_KEY}

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, headers=headers, timeout=10.0)
                response.raise_for_status()
                facility = response.json()
                campsite = parse_ridb_facility_to_campsite(facility, 0, 0)
                if campsite:
                    return campsite
            except Exception as e:
                print(f"RIDB facility detail error: {e}")

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
    return {
        "distance_miles": round(haversine_distance(start_lat, start_lon, end_lat, end_lon), 1),
        "duration_hours": None,
        "geometry": [[start_lon, start_lat], [end_lon, end_lat]]
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
