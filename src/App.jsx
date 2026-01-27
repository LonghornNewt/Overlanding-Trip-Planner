import { useState, useEffect } from 'react';
import './App.css';

const API_BASE = 'https://bug-free-adventure-975px54jxr6pf7pxj-8000.app.github.dev';

function App() {
  const [startLat, setStartLat] = useState('30.27');
  const [startLon, setStartLon] = useState('-97.74');
  const [destLat, setDestLat] = useState('39.74');
  const [destLon, setDestLon] = useState('-104.99');
  const [maxDetour, setMaxDetour] = useState('25');
  const [dailyHours, setDailyHours] = useState('8');
  const [tripPlan, setTripPlan] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // Load Leaflet CSS from CDN
  useEffect(() => {
    const link = document.createElement('link');
    link.rel = 'stylesheet';
    link.href = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css';
    document.head.appendChild(link);
  }, []);

  const planTrip = async () => {
    setLoading(true);
    setError(null);
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

  // Generate static map URL
  const getMapUrl = () => {
    const markers = [];
    markers.push(`pin-l-a+3b82f6(${startLon},${startLat})`);
    markers.push(`pin-l-b+ef4444(${destLon},${destLat})`);
    if (tripPlan) {
      tripPlan.nearby_campsites.forEach(site => {
        markers.push(`pin-s-campsite+22c55e(${site.lon},${site.lat})`);
      });
    }
    const centerLat = (parseFloat(startLat) + parseFloat(destLat)) / 2;
    const centerLon = (parseFloat(startLon) + parseFloat(destLon)) / 2;
    return `https://api.mapbox.com/styles/v1/mapbox/outdoors-v12/static/${markers.join(',')}/auto/800x400?access_token=pk.eyJ1IjoibWFwYm94IiwiYSI6ImNpejY4NXVycTA2emYycXBndHRqcmZ3N3gifQ.rJcFIG214AriISLbB6B5aw`;
  };

  return (
    <div className="app">
      <header className="header">
        <h1>🏕️ Overlanding Trip Planner</h1>
        <p>Plan your next adventure with campsite suggestions for your GX 460</p>
      </header>

      <main className="main">
        {/* Static Map */}
        <section className="map-section">
          <div className="static-map">
            <iframe
              width="100%"
              height="400"
              style={{border: 0, borderRadius: '12px'}}
              loading="lazy"
              src={`https://www.openstreetmap.org/export/embed.html?bbox=${parseFloat(startLon)-5}%2C${parseFloat(startLat)-3}%2C${parseFloat(destLon)+5}%2C${parseFloat(destLat)+3}&layer=mapnik&marker=${startLat}%2C${startLon}`}
            />
          </div>
        </section>

        <section className="trip-form">
          <h2>Plan Your Route</h2>
          <div className="form-grid">
            <div className="form-group">
              <label>Start Location</label>
              <div className="coord-inputs">
                <input type="number" step="0.01" placeholder="Latitude" value={startLat} onChange={(e) => setStartLat(e.target.value)} />
                <input type="number" step="0.01" placeholder="Longitude" value={startLon} onChange={(e) => setStartLon(e.target.value)} />
              </div>
              <span className="hint">Austin, TX: 30.27, -97.74</span>
            </div>
            <div className="form-group">
              <label>Destination</label>
              <div className="coord-inputs">
                <input type="number" step="0.01" placeholder="Latitude" value={destLat} onChange={(e) => setDestLat(e.target.value)} />
                <input type="number" step="0.01" placeholder="Longitude" value={destLon} onChange={(e) => setDestLon(e.target.value)} />
              </div>
              <span className="hint">Denver, CO: 39.74, -104.99</span>
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
              </div>
            </div>

            <div className="segments">
              <h2>Daily Segments</h2>
              {tripPlan.segments.map((segment) => (
                <div key={segment.day} className="segment-card">
                  <div className="segment-header">
                    <h3>Day {segment.day}</h3>
                    <span>{segment.distance_miles} mi • {segment.drive_time_hours} hrs</span>
                  </div>
                  {segment.suggested_campsite && (
                    <div className="campsite-suggestion">
                      <h4>🏕️ {segment.suggested_campsite.name}</h4>
                      <div className="campsite-details">
                        <span className="tag" style={{background: getDifficultyColor(segment.suggested_campsite.difficulty)}}>
                          {segment.suggested_campsite.difficulty || 'Unknown'}
                        </span>
                        <span className="tag" style={{background: getCellServiceColor(segment.suggested_campsite.cell_service)}}>
                          📶 {segment.suggested_campsite.cell_service || 'Unknown'}
                        </span>
                        <span className="tag">{segment.suggested_campsite.elevation}ft</span>
                        <span className="tag">⭐ {segment.suggested_campsite.rating}</span>
                        {segment.suggested_campsite.gx460_accessible && <span className="tag gx460">✓ GX 460 OK</span>}
                      </div>
                      <div className="amenities">
                        {segment.suggested_campsite.amenities.map((a, i) => (
                          <span key={i} className="amenity">{a.replace('_', ' ')}</span>
                        ))}
                      </div>
                      <span className="source">Source: {segment.suggested_campsite.source}</span>
                    </div>
                  )}
                </div>
              ))}
            </div>

            <div className="all-campsites">
              <h2>All Nearby Campsites ({tripPlan.nearby_campsites.length})</h2>
              <div className="campsite-grid">
                {tripPlan.nearby_campsites.map((site) => (
                  <div key={site.id} className="campsite-card">
                    <h4>{site.name}</h4>
                    <span className="type-badge">{site.type}</span>
                    <div className="campsite-details">
                      <span>{site.distance_from_route.toFixed(1)} mi from route</span>
                      <span>{site.elevation}ft</span>
                      <span>⭐ {site.rating}</span>
                    </div>
                    <div className="campsite-details">
                      <span style={{color: getCellServiceColor(site.cell_service)}}>📶 {site.cell_service}</span>
                      <span style={{color: getDifficultyColor(site.difficulty)}}>{site.difficulty}</span>
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