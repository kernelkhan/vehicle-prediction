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

async function updateMapWithLatestEvent() {
  if (!map) return;
  try {
    const response = await axios.get("/api/events");
    const events = response.data;
    if (!events || events.length === 0) return;
    const latest = events[events.length - 1];
    if (!latest.location) return;

    const { latitude, longitude } = latest.location;
    if (marker) {
      marker.setLatLng([latitude, longitude]);
    } else {
      marker = L.marker([latitude, longitude]).addTo(map);
    }
    marker.bindPopup(
      `${latest.risk_level.toUpperCase()} risk<br/>${new Date(latest.timestamp).toLocaleString()}`
    );
    map.setView([latitude, longitude], 15);
  } catch (error) {
    console.warn("Failed to update map", error);
  }
}

document.addEventListener("DOMContentLoaded", () => {
  if (document.getElementById("map")) {
    initMap();
    updateMapWithLatestEvent();
    setInterval(updateMapWithLatestEvent, 10000);
  }
});

