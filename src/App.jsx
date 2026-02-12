import { useState, useRef, useCallback } from 'react';
import './App.css';
import TripMap from './components/TripMap';

const API_BASE = 'https://improved-waddle-jj7xg7wqgvvvc54pq-8000.app.github.dev';

// Nominatim geocoding - free, open, no API key needed
const NOMINATIM_URL = 'https://nominatim.openstreetmap.org/search';

function App() {
  const [startLat, setStartLat] = useState('30.27');
  const [startLon, setStartLon] = useState('-97.74');
  const [destLat, setDestLat] = useState('39.74');
  const [destLon, setDestLon] = useState('-104.99');
  const [startCity, setStartCity] = useState('Austin, TX');
  const [destCity, setDestCity] = useState('Denver, CO');
  const [startSuggestions, setStartSuggestions] = useState([]);
  const [destSuggestions, setDestSuggestions] = useState([]);
  const [maxDetour, setMaxDetour] = useState('25');
  const [dailyHours, setDailyHours] = useState('8');
  const [tripPlan, setTripPlan] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [selectedCampsite, setSelectedCampsite] = useState(null);
  const [searchingStart, setSearchingStart] = useState(false);
  const [searchingDest, setSearchingDest] = useState(false);

  // Debounce refs
  const startTimerRef = useRef(null);
  const destTimerRef = useRef(null);

  // Build a readable short name from Nominatim address details
  const buildShortName = (result) => {
    const addr = result.address || {};
    const city = addr.city || addr.town || addr.village || addr.hamlet || addr.county || '';
    const state = addr.state || '';
    const country = addr.country_code ? addr.country_code.toUpperCase() : '';
    if (city && state) return city + ', ' + state;
    if (city && country) return city + ', ' + country;
    const parts = result.display_name.split(',').map(s => s.trim());
    return parts.slice(0, 2).join(', ');
  };

  // Geocode using Nominatim API - searches anywhere in the world
  const geocodeCity = useCallback(async (query, setSuggestions, setSearching, timerRef) => {
    if (query.length < 3) {
      setSuggestions([]);
      return;
    }

    // Clear previous timer
    if (timerRef.current) clearTimeout(timerRef.current);

    // Debounce 400ms to respect Nominatim usage policy (max 1 req/sec)
    timerRef.current = setTimeout(async () => {
      setSearching(true);
      try {
        const params = new URLSearchParams({
          q: query,
          format: 'json',
          limit: '8',
          addressdetails: '1',
        });
        const res = await fetch(NOMINATIM_URL + '?' + params.toString(), {
          headers: { 'User-Agent': 'OverlandingTripPlanner/1.0' }
        });
        const data = await res.json();
        const suggestions = data.map(r => ({
          name: r.display_name,
          lat: parseFloat(r.lat),
          lon: parseFloat(r.lon),
          shortName: buildShortName(r),
        }));
        setSuggestions(suggestions);
      } catch (err) {
        console.error('Geocoding error:', err);
        setSuggestions([]);
      } finally {
        setSearching(false);
      }
    }, 400);
  }, []);

  const selectStartLocation = (suggestion) => {
    setStartLat(suggestion.lat.toString());
    setStartLon(suggestion.lon.toString());
    setStartCity(suggestion.shortName || suggestion.name);
    setStartSuggestions([]);
  };

  const selectDestLocation = (suggestion) => {
    setDestLat(suggestion.lat.toString());
    setDestLon(suggestion.lon.toString());
    setDestCity(suggestion.shortName || suggestion.name);
    setDestSuggestions([]);
  };

  const planTrip = async () => {
    setLoading(true);
    setError(null);
    setSelectedCampsite(null);

    try {
      const response = await fetch(`${API_BASE}/api/trip/plan`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          start: { lat: parseFloat(startLat), lon: parseFloat(startLon) },
          destination: { lat: parseFloat(destLat), lon: parseFloat(destLon) },
          max_detour_miles: parseFloat(maxDetour),
          daily_drive_hours: parseFloat(dailyHours),
        }),
      });

      if (!response.ok) throw new Error('Failed to plan trip');
      const data = await response.json();
      setTripPlan(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const getCellServiceColor = (service) => {
    const colors = { excellent: '#22c55e', good: '#84cc16', weak: '#eab308', none: '#ef4444' };
    return colors[service] || '#6b7280';
  };

  const getDifficultyColor = (diff) => {
    const colors = { easy: '#22c55e', moderate: '#eab308', difficult: '#ef4444' };
    return colors[diff] || '#6b7280';
  };

  const handleCampsiteSelect = (site) => {
    setSelectedCampsite(site);
    const detailsSection = document.getElementById('campsite-details');
    if (detailsSection) {
      detailsSection.scrollIntoView({ behavior: 'smooth' });
    }
  };

  return (
    <div className="app">
      <header className="header">
        <h1>🏕️ Overlanding Trip Planner</h1>
        <p>Plan your next adventure with campsite suggestions for your GX 460</p>
      </header>

      <main className="main">
        {/* Interactive Map */}
        <section className="map-section">
          <TripMap
            startLat={startLat}
            startLon={startLon}
            destLat={destLat}
            destLon={destLon}
            tripPlan={tripPlan}
            onCampsiteSelect={handleCampsiteSelect}
            selectedCampsite={selectedCampsite}
          />
          <div className="map-legend">
            <span><span className="legend-marker green"></span> Start</span>
            <span><span className="legend-marker red"></span> Destination</span>
            <span><span className="legend-marker orange"></span> Dispersed</span>
            <span><span className="legend-marker blue"></span> Campground</span>
            <span><span className="legend-marker violet"></span> RV Park</span>
          </div>
        </section>

        {/* Trip Form */}
        <section className="trip-form">
          <h2>Plan Your Route</h2>
          <div className="form-grid">
            <div className="form-group">
              <label>Start Location</label>
              <div className="city-search">
                <input
                  type="text"
                  placeholder="Search any city or place..."
                  value={startCity}
                  onChange={(e) => {
                    setStartCity(e.target.value);
                    geocodeCity(e.target.value, setStartSuggestions, setSearchingStart, startTimerRef);
                  }}
                />
                {searchingStart && <span className="searching">Searching...</span>}
                {startSuggestions.length > 0 && (
                  <ul className="suggestions">
                    {startSuggestions.map((s, i) => (
                      <li key={i} onClick={() => selectStartLocation(s)}>
                        <strong>{s.shortName}</strong>
                        <span className="suggestion-full">{s.name}</span>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
              <span className="hint">📍 {startLat}, {startLon}</span>
            </div>

            <div className="form-group">
              <label>Destination</label>
              <div className="city-search">
                <input
                  type="text"
                  placeholder="Search any city or place..."
                  value={destCity}
                  onChange={(e) => {
                    setDestCity(e.target.value);
                    geocodeCity(e.target.value, setDestSuggestions, setSearchingDest, destTimerRef);
                  }}
                />
                {searchingDest && <span className="searching">Searching...</span>}
                {destSuggestions.length > 0 && (
                  <ul className="suggestions">
                    {destSuggestions.map((s, i) => (
                      <li key={i} onClick={() => selectDestLocation(s)}>
                        <strong>{s.shortName}</strong>
                        <span className="suggestion-full">{s.name}</span>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
              <span className="hint">📍 {destLat}, {destLon}</span>
            </div>

            <div className="form-group">
              <label>Max Detour (miles)</label>
              <input type="number" value={maxDetour} onChange={(e) => setMaxDetour(e.target.value)} />
            </div>
            <div className="form-group">
              <label>Daily Drive Hours</label>
              <input type="number" value={dailyHours} onChange={(e) => setDailyHours(e.target.value)} />
            </div>
          </div>

          <button className="plan-btn" onClick={planTrip} disabled={loading}>
            {loading ? 'Planning...' : '🗺️ Plan Trip'}
          </button>

          {error && <p className="error">{error}</p>}
        </section>

        {/* Selected Campsite Details */}
        {selectedCampsite && (
          <section id="campsite-details" className="selected-campsite">
            <h2>📍 Selected Campsite</h2>
            <div className="selected-campsite-card">
              <div className="selected-header">
                <h3>⛺ {selectedCampsite.name}</h3>
                <span className="type-badge">{selectedCampsite.type}</span>
              </div>
              <div className="selected-details">
                <div className="detail-row">
                  <span>⭐ Rating:</span>
                  <span>{selectedCampsite.rating || 'N/A'}</span>
                </div>
                <div className="detail-row">
                  <span>📍 Elevation:</span>
                  <span>{selectedCampsite.elevation?.toLocaleString() || 'N/A'} ft</span>
                </div>
                <div className="detail-row">
                  <span>📶 Cell Service:</span>
                  <span style={{color: getCellServiceColor(selectedCampsite.cell_service)}}>
                    {selectedCampsite.cell_service || 'Unknown'}
                  </span>
                </div>
                <div className="detail-row">
                  <span>🛤️ Difficulty:</span>
                  <span style={{color: getDifficultyColor(selectedCampsite.difficulty)}}>
                    {selectedCampsite.difficulty || 'Unknown'}
                  </span>
                </div>
                <div className="detail-row">
                  <span>🚗 GX 460:</span>
                  <span className={selectedCampsite.gx460_accessible ? 'gx460-ok' : 'gx460-no'}>
                    {selectedCampsite.gx460_accessible ? '✓ Accessible' : '✗ Not Recommended'}
                  </span>
                </div>
                <div className="detail-row">
                  <span>📐 Detour:</span>
                  <span>{selectedCampsite.distance_from_route?.toFixed(1) || '0'} miles</span>
                </div>
              </div>
              <div className="amenities-list">
                <strong>Amenities:</strong>
                <div className="amenity-tags">
                  {selectedCampsite.amenities?.map((a, i) => (
                    <span key={i} className="amenity-tag">{a.replace('_', ' ')}</span>
                  ))}
                  {(!selectedCampsite.amenities || selectedCampsite.amenities.length === 0) && (
                    <span className="amenity-tag none">None listed</span>
                  )}
                </div>
              </div>
              <p className="source">Source: {selectedCampsite.source}</p>
              <button className="clear-selection" onClick={() => setSelectedCampsite(null)}>
                Clear Selection
              </button>
            </div>
          </section>
        )}

        {/* Trip Results */}
        {tripPlan && (
          <section className="results">
            <div className="trip-summary">
              <h2>Trip Summary</h2>
              <div className="summary-stats">
                <div className="stat">
                  <span className="stat-value">{tripPlan.total_distance_miles}</span>
                  <span className="stat-label">Total Miles</span>
                </div>
                <div className="stat">
                  <span className="stat-value">{tripPlan.total_drive_time_hours.toFixed(1)}</span>
                  <span className="stat-label">Drive Hours</span>
                </div>
                <div className="stat">
                  <span className="stat-value">{tripPlan.segments.length}</span>
                  <span className="stat-label">Days</span>
                </div>
                <div className="stat">
                  <span className="stat-value">{tripPlan.nearby_campsites.length}</span>
                  <span className="stat-label">Campsites Found</span>
                </div>
              </div>
            </div>

            {/* Directions */}
            {tripPlan.directions && tripPlan.directions.length > 0 && (
              <div className="directions">
                <h2>🧭 Directions</h2>
                <ol className="directions-list">
                  {tripPlan.directions.map((dir, i) => (
                    <li key={i} className="direction-item">
                      <span className="direction-icon">
                        {dir.maneuver_type === 'turn' && dir.maneuver_modifier === 'left' && '↰'}
                        {dir.maneuver_type === 'turn' && dir.maneuver_modifier === 'right' && '↱'}
                        {dir.maneuver_type === 'merge' && '⤨'}
                        {dir.maneuver_type === 'fork' && '⑂'}
                        {dir.maneuver_type === 'depart' && '🚗'}
                        {dir.maneuver_type === 'arrive' && '🏁'}
                        {!['turn', 'merge', 'fork', 'depart', 'arrive'].includes(dir.maneuver_type) && '→'}
                      </span>
                      <div className="direction-content">
                        <span className="direction-road">
                          {dir.ref && <strong>{dir.ref}</strong>}
                          {dir.ref && dir.instruction && ' - '}
                          {dir.instruction || dir.maneuver_type}
                        </span>
                        <span className="direction-meta">
                          {dir.distance_miles} mi • {dir.duration_minutes} min
                        </span>
                      </div>
                    </li>
                  ))}
                </ol>
              </div>
            )}

            <div className="segments">
              <h2>🛣️ Daily Itinerary</h2>
              <p className="segments-hint">Based on {dailyHours} hours of driving per day</p>
              {tripPlan.segments.map((segment) => (
                <div key={segment.day} className="segment-card">
                  <div className="segment-header">
                    <h3>Day {segment.day}</h3>
                    <span>{segment.distance_miles} mi • {segment.drive_time_hours} hrs driving</span>
                  </div>
                  <div className="segment-stop">
                    <span className="stop-label">📍 Stop for the night near:</span>
                    <span className="stop-location">
                      {segment.end_point.lat.toFixed(2)}°N, {Math.abs(segment.end_point.lon).toFixed(2)}°W
                    </span>
                  </div>
                  {segment.suggested_campsite ? (
                    <div
                      className={`campsite-suggestion ${selectedCampsite?.id === segment.suggested_campsite.id ? 'selected' : ''}`}
                      onClick={() => handleCampsiteSelect(segment.suggested_campsite)}
                    >
                      <div className="suggestion-header">
                        <h4>⛺ Recommended: {segment.suggested_campsite.name}</h4>
                        <span className="detour-badge">
                          {segment.suggested_campsite.distance_from_route?.toFixed(1) || '0'} mi detour
                        </span>
                      </div>
                      <div className="campsite-details">
                        <span className="tag" style={{background: getDifficultyColor(segment.suggested_campsite.difficulty)}}>
                          {segment.suggested_campsite.difficulty || 'Unknown'}
                        </span>
                        <span className="tag" style={{background: getCellServiceColor(segment.suggested_campsite.cell_service)}}>
                          📶 {segment.suggested_campsite.cell_service || 'Unknown'}
                        </span>
                        {segment.suggested_campsite.rating && (
                          <span className="tag">⭐ {segment.suggested_campsite.rating}</span>
                        )}
                        {segment.suggested_campsite.gx460_accessible && <span className="tag gx460">✓ GX 460</span>}
                      </div>
                      <div className="amenities">
                        {segment.suggested_campsite.amenities.map((a, i) => (
                          <span key={i} className="amenity">{a.replace('_', ' ')}</span>
                        ))}
                      </div>
                      <span className="source">Source: {segment.suggested_campsite.source}</span>
                    </div>
                  ) : (
                    <div className="no-campsite">
                      <p>No campsites found within {maxDetour} miles of this stop</p>
                    </div>
                  )}
                </div>
              ))}
            </div>

            <div className="all-campsites">
              <h2>All Nearby Campsites ({tripPlan.nearby_campsites.length})</h2>
              <p className="campsite-hint">Click a marker on the map or a card below for details</p>
              <div className="campsite-grid">
                {tripPlan.nearby_campsites.map((site) => (
                  <div
                    key={site.id}
                    className={`campsite-card ${selectedCampsite?.id === site.id ? 'selected' : ''}`}
                    onClick={() => handleCampsiteSelect(site)}
                  >
                    <h4>{site.name}</h4>
                    <span className="type-badge">{site.type}</span>
                    <div className="campsite-details">
                      <span style={{color: getCellServiceColor(site.cell_service)}}>📶 {site.cell_service}</span>
                      <span style={{color: getDifficultyColor(site.difficulty)}}>{site.difficulty}</span>
                      <span>⭐ {site.rating}</span>
                      {site.gx460_accessible && <span className="gx460-ok">✓ GX 460</span>}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </section>
        )}
      </main>
    </div>
  );
}

export default App;
