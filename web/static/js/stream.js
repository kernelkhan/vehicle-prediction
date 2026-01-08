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

  // Deduplicate events: only show unique events (by track_id + timestamp within 1 second)
  const uniqueEvents = [];
  const seen = new Set();
  
  events.slice().reverse().forEach((event) => {
    const key = `${event.track_id}_${Math.floor(new Date(event.timestamp).getTime() / 1000)}`;
    if (!seen.has(key)) {
      seen.add(key);
      uniqueEvents.push(event);
    }
  });

  uniqueEvents.slice(0, 10).forEach((event) => {
    const item = document.createElement("li");
    const timeStr = new Date(event.timestamp).toLocaleTimeString();
    const reasons = event.reasons.length > 0 ? event.reasons.join(", ") : "risk detected";
    const riskBadge = `<span class="badge ${event.risk_level}">${event.risk_level.toUpperCase()}</span>`;
    
    item.innerHTML = `
      <div class="event-item">
        <div class="event-header">
          ${riskBadge}
          <span class="event-time">${timeStr}</span>
          <span class="event-score">Score: ${event.risk_score.toFixed(2)}</span>
        </div>
        <div class="event-details">
          Track ${event.track_id} · ${reasons}
        </div>
      </div>
    `;
    list.appendChild(item);
  });
}

function updateRiskStatus(events) {
  const status = document.getElementById("risk-status");
  if (!status) return;
  
  const statusDiv = status.parentElement;
  
  if (events.length === 0) {
    status.textContent = "Risk Status: --";
    if (statusDiv) {
      statusDiv.className = "status";
    }
    return;
  }
  
  const latest = events[events.length - 1];
  status.textContent = `Risk Status: ${latest.risk_level.toUpperCase()} (${latest.risk_score.toFixed(2)})`;
  
  // Update parent status div with risk level class
  if (statusDiv) {
    statusDiv.className = `status ${latest.risk_level}`;
  }
}

async function refreshDashboard() {
  const events = await pollEvents();
  updateTimeline(events);
  updateRiskStatus(events);
}

function initVideoStream() {
  const img = document.getElementById("live-stream");
  const placeholder = document.getElementById("video-placeholder");
  if (!img || !placeholder) return;

  let errorCount = 0;
  const maxErrors = 3;

  img.onload = function() {
    errorCount = 0;
    placeholder.classList.add("hidden");
    img.style.display = "block";
  };

  img.onerror = function() {
    errorCount++;
    if (errorCount >= maxErrors) {
      placeholder.classList.remove("hidden");
      img.style.display = "none";
    } else {
      // Retry after a short delay
      setTimeout(() => {
        img.src = "/video-feed?t=" + Date.now();
      }, 1000);
    }
  };

  // Initial load
  img.src = "/video-feed?t=" + Date.now();
  
  // Refresh stream every 30 seconds to prevent stale connections
  setInterval(() => {
    if (img.style.display !== "none") {
      img.src = "/video-feed?t=" + Date.now();
    }
  }, 30000);
}

document.addEventListener("DOMContentLoaded", () => {
  if (document.getElementById("live-stream")) {
    initVideoStream();
    refreshDashboard();
    setInterval(refreshDashboard, 5000);
  }
});

