import { MapContainer, TileLayer, Marker, Popup, Polyline, useMap } from 'react-leaflet';
import { useEffect } from 'react';
import L from 'leaflet';

// Fix for default marker icons in React-Leaflet
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon-2x.png',
  iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png',
});

// Custom icons for different marker types
const createIcon = (color) => new L.Icon({
  iconUrl: `https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-${color}.png`,
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png',
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  popupAnchor: [1, -34],
  shadowSize: [41, 41]
});

const icons = {
  start: createIcon('green'),
  end: createIcon('red'),
  dispersed: createIcon('orange'),
  campground: createIcon('blue'),
  rv_park: createIcon('violet'),
  default: createIcon('grey')
};

// Component to fit map bounds when data changes
function FitBounds({ bounds }) {
  const map = useMap();
  
  useEffect(() => {
    if (bounds && bounds.length > 0) {
      map.fitBounds(bounds, { padding: [50, 50] });
    }
  }, [map, bounds]);
  
  return null;
}

function TripMap({ 
  startLat, 
  startLon, 
  destLat, 
  destLon, 
  tripPlan, 
  onCampsiteSelect,
  selectedCampsite 
}) {
  // Calculate center and bounds
  const centerLat = (parseFloat(startLat) + parseFloat(destLat)) / 2;
  const centerLon = (parseFloat(startLon) + parseFloat(destLon)) / 2;
  
  // Build bounds array for auto-fit
  const allPoints = [
    [parseFloat(startLat), parseFloat(startLon)],
    [parseFloat(destLat), parseFloat(destLon)]
  ];
  
  if (tripPlan?.nearby_campsites) {
    tripPlan.nearby_campsites.forEach(site => {
      allPoints.push([site.lat, site.lon]);
    });
  }

  // Convert OSRM geometry [lon, lat] to Leaflet [lat, lon]
  const getRoutePositions = () => {
    if (tripPlan?.route_geometry && tripPlan.route_geometry.length > 0) {
      // OSRM returns [lon, lat], Leaflet needs [lat, lon]
      return tripPlan.route_geometry.map(coord => [coord[1], coord[0]]);
    }
    
    // Fallback to straight line
    return [
      [parseFloat(startLat), parseFloat(startLon)],
      [parseFloat(destLat), parseFloat(destLon)]
    ];
  };

  const routePositions = getRoutePositions();

  const getCampsiteIcon = (type) => icons[type] || icons.default;

  const formatAmenities = (amenities) => {
    if (!amenities || amenities.length === 0) return 'None listed';
    return amenities.map(a => a.replace('_', ' ')).join(', ');
  };

  return (
    <MapContainer 
      center={[centerLat, centerLon]} 
      zoom={6} 
      style={{ height: '450px', width: '100%', borderRadius: '12px' }}
    >
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      
      <FitBounds bounds={allPoints} />
      
      {/* Start marker */}
      <Marker position={[parseFloat(startLat), parseFloat(startLon)]} icon={icons.start}>
        <Popup>
          <div className="map-popup">
            <strong>🚀 Start Location</strong>
            <p>{startLat}, {startLon}</p>
          </div>
        </Popup>
      </Marker>
      
      {/* End marker */}
      <Marker position={[parseFloat(destLat), parseFloat(destLon)]} icon={icons.end}>
        <Popup>
          <div className="map-popup">
            <strong>🏁 Destination</strong>
            <p>{destLat}, {destLon}</p>
          </div>
        </Popup>
      </Marker>
      
      {/* Actual driving route from OSRM */}
      <Polyline 
        positions={routePositions} 
        color="#3b82f6" 
        weight={4} 
        opacity={0.8}
      />
      
      {/* Campsite markers */}
      {tripPlan?.nearby_campsites?.map(site => (
        <Marker 
          key={site.id} 
          position={[site.lat, site.lon]}
          icon={getCampsiteIcon(site.type)}
          eventHandlers={{
            click: () => onCampsiteSelect && onCampsiteSelect(site)
          }}
        >
          <Popup>
            <div className="map-popup">
              <strong>⛺ {site.name}</strong>
              <p className="popup-type">{site.type.replace('_', ' ')}</p>
              {site.rating && <p>⭐ {site.rating} / 5</p>}
              {site.elevation && <p>📍 {site.elevation.toLocaleString()} ft</p>}
              {site.cell_service && <p>📶 {site.cell_service}</p>}
              {site.difficulty && <p>🛤️ {site.difficulty}</p>}
              <p className="popup-amenities">
                <strong>Amenities:</strong> {formatAmenities(site.amenities)}
              </p>
              {site.gx460_accessible && (
                <p className="popup-gx460">✓ GX 460 Accessible</p>
              )}
              <p className="popup-source">Source: {site.source}</p>
              {onCampsiteSelect && (
                <button 
                  className="popup-select-btn"
                  onClick={() => onCampsiteSelect(site)}
                >
                  View Details
                </button>
              )}
            </div>
          </Popup>
        </Marker>
      ))}
      
      {/* Highlight selected campsite */}
      {selectedCampsite && (
        <Marker 
          position={[selectedCampsite.lat, selectedCampsite.lon]}
          icon={createIcon('gold')}
        >
          <Popup>
            <div className="map-popup selected">
              <strong>⭐ {selectedCampsite.name}</strong>
              <p>Currently selected</p>
            </div>
          </Popup>
        </Marker>
      )}
    </MapContainer>
  );
}

export default TripMap;
