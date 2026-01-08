/* global axios, L */

let map;
let marker;

function initMap() {
  const mapContainer = document.getElementById("map");
  if (!mapContainer) return;

  map = L.map("map").setView([20.5937, 78.9629], 5); // India centroid fallback
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
    attribution: "© OpenStreetMap contributors",
  }).addTo(map);
}

let markers = [];

async function updateMapWithLatestEvent() {
  if (!map) return;
  try {
    const response = await axios.get("/api/events");
    const events = response.data;
    if (!events || events.length === 0) {
      // Use default location (India center) if no events
      if (markers.length === 0) {
        const defaultLat = 20.5937;
        const defaultLon = 78.9629;
        const defaultMarker = L.marker([defaultLat, defaultLon]).addTo(map);
        defaultMarker.bindPopup("No events yet. Waiting for detection...");
        markers.push(defaultMarker);
        map.setView([defaultLat, defaultLon], 5);
      }
      return;
    }

    // Clear existing markers
    markers.forEach(m => map.removeLayer(m));
    markers = [];

    // Add markers for all events with location data
    const eventsWithLocation = events.filter(e => e.location && e.location.latitude && e.location.longitude);
    
    if (eventsWithLocation.length === 0) {
      // If no location data, check if we have any events at all
      if (events.length > 0) {
        // Use default location for events without GPS
        const defaultLat = 20.5937;
        const defaultLon = 78.9629;
        const defaultMarker = L.marker([defaultLat, defaultLon], {
          icon: getMarkerIcon(events[events.length - 1].risk_level)
        }).addTo(map);
        const latestEvent = events[events.length - 1];
        defaultMarker.bindPopup(
          `<strong>${latestEvent.risk_level.toUpperCase()} Risk</strong><br/>
           ${events.length} event(s) detected<br/>
           <small>No GPS data available</small>`
        );
        markers.push(defaultMarker);
        map.setView([defaultLat, defaultLon], 5);
      }
      return;
    }

    // Add markers for each event
    eventsWithLocation.forEach((event, index) => {
      const { latitude, longitude } = event.location;
      const eventMarker = L.marker([latitude, longitude], {
        icon: getMarkerIcon(event.risk_level)
      }).addTo(map);
      
      const timeStr = new Date(event.timestamp).toLocaleString();
      const reasons = event.reasons.length > 0 ? event.reasons.join(", ") : "risk detected";
      eventMarker.bindPopup(
        `<strong>${event.risk_level.toUpperCase()} Risk</strong><br/>
         Track: ${event.track_id}<br/>
         Score: ${event.risk_score.toFixed(2)}<br/>
         ${reasons}<br/>
         <small>${timeStr}</small>`
      );
      markers.push(eventMarker);
    });

    // Focus on the latest event
    const latest = eventsWithLocation[eventsWithLocation.length - 1];
    if (latest && latest.location) {
      map.setView([latest.location.latitude, latest.location.longitude], 13);
    }
  } catch (error) {
    console.warn("Failed to update map", error);
  }
}

function getMarkerIcon(riskLevel) {
  const colors = {
    low: "#58a6ff",
    medium: "#f1c40f",
    high: "#e67e22",
    critical: "#e74c3c"
  };
  const color = colors[riskLevel] || "#8b949e";
  
  return L.divIcon({
    className: "custom-marker",
    html: `<div style="background-color: ${color}; width: 20px; height: 20px; border-radius: 50%; border: 2px solid white; box-shadow: 0 2px 4px rgba(0,0,0,0.3);"></div>`,
    iconSize: [20, 20],
    iconAnchor: [10, 10]
  });
}

document.addEventListener("DOMContentLoaded", () => {
  if (document.getElementById("map")) {
    initMap();
    updateMapWithLatestEvent();
    // Update map more frequently to show new events
    setInterval(updateMapWithLatestEvent, 5000);
  }
});

