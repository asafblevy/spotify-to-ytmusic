// State
let ytPollTimer = null;

// --- Init ---
async function init() {
  const res = await fetch("/auth/status");
  const data = await res.json();

  if (data.spotify) {
    document.getElementById("spotify-disconnected").classList.add("hidden");
    document.getElementById("spotify-connected").classList.remove("hidden");
  }
  if (data.ytmusic) {
    document.getElementById("yt-disconnected").classList.add("hidden");
    document.getElementById("yt-device-code").classList.add("hidden");
    document.getElementById("yt-connected").classList.remove("hidden");
  }
  if (data.spotify && data.ytmusic) {
    loadPreview();
  }
}

// --- YouTube Music Auth ---
async function startYTAuth() {
  const res = await fetch("/auth/ytmusic/start", { method: "POST" });
  const data = await res.json();

  document.getElementById("yt-disconnected").classList.add("hidden");
  document.getElementById("yt-device-code").classList.remove("hidden");
  document.getElementById("yt-code").textContent = data.user_code;
  const link = document.getElementById("yt-link");
  link.href = data.verification_url;
  link.textContent = data.verification_url;

  // Start polling
  ytPollTimer = setInterval(pollYTAuth, 5000);
}

async function pollYTAuth() {
  const res = await fetch("/auth/ytmusic/poll");
  const data = await res.json();
  if (data.status === "complete") {
    clearInterval(ytPollTimer);
    document.getElementById("yt-device-code").classList.add("hidden");
    document.getElementById("yt-connected").classList.remove("hidden");
    // Check if both connected
    const authRes = await fetch("/auth/status");
    const authData = await authRes.json();
    if (authData.spotify && authData.ytmusic) {
      loadPreview();
    }
  }
}

// --- Library Preview ---
async function loadPreview() {
  document.getElementById("preview-section").classList.remove("hidden");
  const res = await fetch("/library/preview");
  const data = await res.json();
  document.getElementById("stat-liked").textContent = data.liked_songs ?? "?";
  document.getElementById("stat-playlists").textContent = data.playlists ?? "?";
  document.getElementById("stat-artists").textContent = data.artists ?? "?";
}

// --- Transfer ---
async function startTransfer() {
  const options = {
    liked_songs: document.getElementById("opt-liked").checked,
    playlists: document.getElementById("opt-playlists").checked,
    artists: document.getElementById("opt-artists").checked,
  };

  document.getElementById("preview-section").classList.add("hidden");
  document.getElementById("auth-section").classList.add("hidden");
  document.getElementById("progress-section").classList.remove("hidden");

  await fetch("/transfer/start", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(options),
  });

  // Listen for progress via SSE
  const evtSource = new EventSource("/transfer/progress");
  evtSource.addEventListener("progress", (e) => {
    const state = JSON.parse(e.data);
    updateProgress(state);
    if (state.done) {
      evtSource.close();
      showDone(state);
    }
  });
  evtSource.onerror = () => {
    evtSource.close();
  };
}

function updateProgress(state) {
  document.getElementById("phase-text").textContent = state.phase || "Working...";
  const total = state.total || 1;
  const pct = Math.round((state.processed / total) * 100);
  document.getElementById("progress-fill").style.width = pct + "%";
  document.getElementById("cnt-processed").textContent = state.processed || 0;
  document.getElementById("cnt-matched").textContent = state.matched || 0;
  document.getElementById("cnt-failed").textContent = (state.failed_tracks || []).length;

  // Update log
  const logEl = document.getElementById("log");
  const logs = state.log || [];
  logEl.innerHTML = logs.map((l) => "<div>" + escHtml(l) + "</div>").join("");
  logEl.scrollTop = logEl.scrollHeight;
}

function showDone(state) {
  document.getElementById("progress-section").classList.add("hidden");
  document.getElementById("done-section").classList.remove("hidden");

  if (state.error) {
    document.getElementById("done-section").querySelector("h3").textContent = "Transfer Failed";
    document.getElementById("done-section").querySelector("h3").style.color = "#ef5350";
    document.getElementById("final-matched").parentElement.innerHTML =
      '<span style="color:#ef5350">' + escHtml(state.error) + '</span>';
    // Show log for debugging
    const logs = state.log || [];
    if (logs.length > 0) {
      const logHtml = logs.map((l) => "<div>" + escHtml(l) + "</div>").join("");
      const logDiv = document.createElement("div");
      logDiv.className = "log";
      logDiv.innerHTML = logHtml;
      document.getElementById("done-section").querySelector(".card").appendChild(logDiv);
    }
    return;
  }

  document.getElementById("final-matched").textContent = state.matched || 0;
  const failed = state.failed_tracks || [];
  document.getElementById("final-failed").textContent = failed.length;

  if (failed.length > 0) {
    document.getElementById("failed-list-container").classList.remove("hidden");
    document.getElementById("failed-count").textContent = failed.length;
    const listEl = document.getElementById("failed-list");
    listEl.innerHTML = failed.map((f) => "<div>" + escHtml(f) + "</div>").join("");
  }

  // Show log summary
  const logs = state.log || [];
  if (logs.length > 0) {
    const logHtml = logs.map((l) => "<div>" + escHtml(l) + "</div>").join("");
    const logDiv = document.createElement("div");
    logDiv.className = "log";
    logDiv.innerHTML = logHtml;
    document.getElementById("done-section").querySelector(".card").appendChild(logDiv);
  }
}

function toggleFailed() {
  const el = document.getElementById("failed-list");
  el.classList.toggle("hidden");
}

async function logout() {
  await fetch("/auth/logout", { method: "POST" });
  location.reload();
}

function escHtml(s) {
  const d = document.createElement("div");
  d.textContent = s;
  return d.innerHTML;
}

// Start
init();
