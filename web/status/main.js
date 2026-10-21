// Home status page: gets items from /api/status, draws them, counts down locally.
// ?demo=<scenario> shows fake data. ?static=1 fetches once (for screenshots).
// ?view=detail adds a header clock and more facts per item, for big screens.
import { clockHtml, updateClock } from "./clock.js";
import { ROTATE_MS, itemsOnPage, pageCount, pickLayout } from "./layout.js";
import { tileHtml, updateTimes } from "./ring.js";

const screen = document.getElementById("screen");
const header = document.getElementById("header");
const offline = document.getElementById("offline");
const params = new URLSearchParams(location.search);
const query = params.has("demo") ? `?demo=${encodeURIComponent(params.get("demo"))}` : "";
const detail = params.get("view") === "detail";
document.body.dataset.view = detail ? "detail" : "simple";

let data = null;
let clockOffset = 0; // server time minus this device's time, in seconds
let page = 0;

const now = () => Date.now() / 1000 + clockOffset;
const shown = () => itemsOnPage(data.items, page);

function render() {
  const items = shown();
  const layout = pickLayout(items.length);
  screen.dataset.layout = layout;
  screen.innerHTML = layout === "idle"
    ? clockHtml()
    : items.map((item, slot) => tileHtml(item, slot, { withCover: layout === "one", detail, tz: data.tz })).join("");
  // Detail view keeps a small clock on top while things run.
  header.hidden = !detail || layout === "idle";
  header.innerHTML = header.hidden ? "" : `${clockHtml()}<div class="page"></div>`;
  const pages = pageCount(data.items);
  if (!header.hidden && pages > 1) header.querySelector(".page").textContent = `${page % pages + 1} / ${pages}`;
  offline.hidden = data.connected || data.demo != null;
  tick();
}

function tick() {
  updateTimes(screen, shown(), now());
  updateClock(screen, now(), data.tz);
  updateClock(header, now(), data.tz);
}

function receive(snapshot) {
  data = snapshot;
  clockOffset = data.now - Date.now() / 1000;
  render();
}

if (params.has("static")) {
  fetch(`/api/status${query}`).then((r) => r.json()).then(receive);
} else {
  new EventSource(`/api/status/stream${query}`).onmessage = (e) => receive(JSON.parse(e.data));
  setInterval(() => data && tick(), 1000);
  setInterval(() => {
    if (data && pageCount(data.items) > 1) {
      page++;
      render();
    }
  }, ROTATE_MS);
}
