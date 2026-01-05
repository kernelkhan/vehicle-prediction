/* global axios */

async function pollEvents() {
  try {
    const response = await axios.get("/api/events");
    return response.data;
  } catch (error) {
    console.error("Failed to load events", error);
    return [];
  }
}

function updateTimeline(events) {
  const list = document.getElementById("event-list");
  if (!list) return;
  list.innerHTML = "";

  events.slice(-5).reverse().forEach((event) => {
    const item = document.createElement("li");
    item.innerHTML = `
      <strong>${event.risk_level.toUpperCase()}</strong> · ${new Date(event.timestamp).toLocaleTimeString()} · track ${event.track_id} · ${event.reasons.join(", ")}
    `;
    list.appendChild(item);
  });
}

function updateRiskStatus(events) {
  const status = document.getElementById("risk-status");
  if (!status) return;
  if (events.length === 0) {
    status.textContent = "Risk Status: --";
    return;
  }
  const latest = events[events.length - 1];
  status.textContent = `Risk Status: ${latest.risk_level.toUpperCase()} (${latest.risk_score.toFixed(2)})`;
  status.className = `status ${latest.risk_level}`;
}

async function refreshDashboard() {
  const events = await pollEvents();
  updateTimeline(events);
  updateRiskStatus(events);
}

document.addEventListener("DOMContentLoaded", () => {
  if (document.getElementById("live-stream")) {
    refreshDashboard();
    setInterval(refreshDashboard, 5000);
  }
});

