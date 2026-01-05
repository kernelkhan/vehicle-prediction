/* global axios */

async function fetchEvents() {
  try {
    const response = await axios.get("/api/events");
    return response.data;
  } catch (error) {
    console.error("Failed to fetch events", error);
    return [];
  }
}

function renderEventTable(events) {
  const tableBody = document.querySelector("#event-table tbody");
  if (!tableBody) return;
  tableBody.innerHTML = "";

  events.forEach((event) => {
    const row = document.createElement("tr");
    row.innerHTML = `
      <td>${new Date(event.timestamp).toLocaleString()}</td>
      <td><span class="badge ${event.risk_level}">${event.risk_level}</span></td>
      <td>${event.track_id}</td>
      <td>${event.reasons.join(", ")}</td>
      <td>${event.snapshot_path ? `<a href="${event.snapshot_path}" target="_blank">View</a>` : "—"}</td>
      <td>${event.location ? `<button class="map-link" data-lat="${event.location.latitude}" data-lon="${event.location.longitude}">View</button>` : "—"}</td>
    `;
    tableBody.appendChild(row);
  });
}

async function initEventsPage() {
  const events = await fetchEvents();
  renderEventTable(events);

  document.querySelectorAll(".map-link").forEach((button) => {
    button.addEventListener("click", () => {
      const lat = parseFloat(button.dataset.lat);
      const lon = parseFloat(button.dataset.lon);
      if (!Number.isNaN(lat) && !Number.isNaN(lon)) {
        window.location.href = `https://www.openstreetmap.org/?mlat=${lat}&mlon=${lon}#map=18/${lat}/${lon}`;
      }
    });
  });
}

document.addEventListener("DOMContentLoaded", () => {
  if (document.querySelector("#event-table")) {
    initEventsPage();
  }
});

