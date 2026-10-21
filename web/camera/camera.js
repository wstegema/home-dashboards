// Refreshes one camera snapshot every few seconds. Each new frame loads
// off-screen first, so the picture never blanks between frames.
const params = new URLSearchParams(location.search);
const entity = params.get("entity") || "";
const everyMs = Math.max(1, Number(params.get("every")) || 3) * 1000;

const picture = document.getElementById("picture");
const offline = document.getElementById("offline");
document.getElementById("name").textContent = params.get("name") || "";
document.title = params.get("name") || entity || "Camera";

const url = () => `/api/camera/${encodeURIComponent(entity)}?t=${Date.now()}`;
let loading = false;

function refresh() {
  if (loading || document.hidden) return;
  loading = true;
  const next = new Image();
  next.onload = () => { picture.src = next.src; offline.hidden = true; loading = false; };
  next.onerror = () => { offline.hidden = false; loading = false; };
  next.src = url();
}

if (!entity.startsWith("camera.")) {
  offline.textContent = "Add ?entity=camera.<name> to the URL";
  offline.hidden = false;
} else {
  refresh();
  setInterval(refresh, everyMs);
}
