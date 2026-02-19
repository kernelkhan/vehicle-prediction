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

  // Diff check: simple checksum or length check could be added here for performance
  // For now, we rebuild if list size changed or always rebuild top 10 for simplicity

  list.innerHTML = "";

  uniqueEvents.slice(0, 10).forEach((event) => {
    const item = document.createElement("div");
    item.className = "event-card"; // New card class

    const dateObj = new Date(event.timestamp);
    const timeStr = dateObj.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    const reasons = event.reasons.length > 0 ? event.reasons.join(", ") : "Unsafe behavior detected";
    const riskClass = event.risk_level.toLowerCase(); // Ensure lowercase for CSS

    item.innerHTML = `
        <div class="event-card-header">
            <span class="event-badge bg-${riskClass}">${event.risk_level.toUpperCase()}</span>
            <span class="event-time">${timeStr}</span>
        </div>
        <div class="event-body">
            ID #${event.track_id}: ${reasons}
        </div>
        <div class="event-meta">
            <span>Score: ${event.risk_score.toFixed(2)}</span>
        </div>
    `;
    list.appendChild(item);
  });
}

function updateRiskStatus(events) {
  const statusContainer = document.querySelector(".status"); // Old selector might be gone, check HTML update below
  const riskStatusText = document.getElementById("risk-status");
  const statusDot = document.querySelector(".status-dot");

  // If the new HTML structure isn't there yet, this might fail gracefully or needs HTML update first.
  // Assuming HTML update comes next or is compatible.

  if (!riskStatusText) return; // HTML not ready

  if (events.length === 0) {
    riskStatusText.textContent = "System Active - No Recent Risks";
    if (statusDot) {
      statusDot.className = "status-dot"; // remove active/color classes
      statusDot.style.color = "var(--text-secondary)";
    }
    return;
  }

  const latest = events[events.length - 1];
  // Check if latest event is recent (< 5 seconds ago) to show active status
  const now = new Date();
  const eventTime = new Date(latest.timestamp);
  const isRecent = (now - eventTime) < 5000;

  if (isRecent) {
    riskStatusText.textContent = `Alert: ${latest.risk_level.toUpperCase()} (${latest.risk_score.toFixed(2)})`;
    riskStatusText.className = latest.risk_level; // Add color class to text

    if (statusDot) {
      statusDot.className = `status-dot active ${latest.risk_level}`; // Pulse effect
      statusDot.style.color = ""; // let CSS handle color via class
    }
  } else {
    riskStatusText.textContent = "System Active - Monitoring";
    riskStatusText.className = "";
    if (statusDot) {
      statusDot.className = "status-dot active low"; // Green pulse for normal monitoring
    }
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

  img.onload = function () {
    errorCount = 0;
    placeholder.classList.add("hidden");
    img.style.display = "block";
  };

  img.onerror = function () {
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
    checkPlaybackStatus();
    setInterval(refreshDashboard, 5000);

    // Bind play pause button
    const btn = document.getElementById("play-pause-btn");
    if (btn) {
      btn.addEventListener("click", togglePlayback);
    }
  }
});

let isPaused = false;

async function checkPlaybackStatus() {
  try {
    const response = await axios.get("/api/control/status");
    console.log("Playback status:", response.data);
    isPaused = response.data.paused;
    updatePlayButtonState();
  } catch (e) {
    console.error("Failed to check status", e);
  }
}

function updatePlayButtonState() {
  const iconPause = document.getElementById("icon-pause");
  const iconPlay = document.getElementById("icon-play");
  if (!iconPause || !iconPlay) return;

  if (isPaused) {
    iconPause.style.display = "none";
    iconPlay.style.display = "block";
  } else {
    iconPause.style.display = "block";
    iconPlay.style.display = "none";
  }
}

async function togglePlayback() {
  const btn = document.getElementById("play-pause-btn");

  try {
    console.log("Toggling playback, current:", isPaused);
    if (isPaused) {
      await axios.post("/api/control/resume");
      isPaused = false;
    } else {
      await axios.post("/api/control/pause");
      isPaused = true;
    }
    updatePlayButtonState();

    // Add subtle click effect
    if (btn) {
      btn.style.transform = "scale(0.9)";
      setTimeout(() => btn.style.transform = "scale(1)", 150);
    }
  } catch (error) {
    console.error("Failed to toggle playback:", error);
  }
}
window.togglePlayback = togglePlayback;
