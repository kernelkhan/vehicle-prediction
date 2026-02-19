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


let allEvents = [];

function renderEventTable(events) {
  const tableBody = document.querySelector("#event-table tbody");
  if (!tableBody) return;
  tableBody.innerHTML = "";

  events.forEach((event) => {
    const row = document.createElement("tr");
    row.innerHTML = `
      <td>${new Date(event.timestamp).toLocaleString()}</td>
      <td><span class="event-badge bg-${event.risk_level}">${event.risk_level.toUpperCase()}</span></td>
      <td>${event.track_id}</td>
      <td>${event.reasons.join(", ")}</td>
      <td>${event.snapshot_path ? `<a href="${event.snapshot_path}" target="_blank" class="btn-link">View</a>` : "—"}</td>
      <td>${event.location ? `<button class="btn-link map-link" data-lat="${event.location.latitude}" data-lon="${event.location.longitude}">View</button>` : "—"}</td>
    `;
    tableBody.appendChild(row);
  });
}


function exportCSV() {
  if (!allEvents.length) return alert("No events to export.");

  let csvContent = "data:text/csv;charset=utf-8,";
  csvContent += "Event ID,Timestamp,Risk Level,Track ID,Reasons,Snapshot\n";

  allEvents.forEach(e => {
    const row = [
      e.event_id,
      e.timestamp,
      e.risk_level,
      e.track_id,
      `"${e.reasons.join('; ')}"`,
      e.snapshot_path || ""
    ].join(",");
    csvContent += row + "\n";
  });

  const encodedUri = encodeURI(csvContent);
  const link = document.createElement("a");
  link.setAttribute("href", encodedUri);
  link.setAttribute("download", `events_export_${new Date().toISOString().slice(0, 10)}.csv`);
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
}
window.exportCSV = exportCSV;

async function initEventsPage() {
  allEvents = await fetchEvents();
  renderEventTable(allEvents);

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

// Initialize
function init() {
  if (document.querySelector("#event-table")) {
    initEventsPage();
  }
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", init);
} else {
  init(); // DOM already ready
}

