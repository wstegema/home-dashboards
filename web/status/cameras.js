// Camera pictures (detail view): the side column, and refreshing every live
// <img data-live> on the page. Each refresh loads the new frame off-screen
// first, so the picture never blanks out between frames.
import { escapeHtml } from "./format.js";

export const CAMERA_REFRESH_MS = 3000;

export function camerasHtml(cameras) {
  return cameras.map((cam) => `<figure class="camera">
    <img data-live src="${escapeHtml(cam.url)}" alt="">
    <figcaption>${escapeHtml(cam.name)}</figcaption>
  </figure>`).join("");
}

export function refreshLive(root = document) {
  root.querySelectorAll("img[data-live]").forEach((img) => {
    if (img.dataset.loading) return; // previous frame still on its way
    const base = img.src.split(/[?#]/)[0];
    const next = new Image();
    img.dataset.loading = "1";
    next.onload = () => { img.src = next.src; delete img.dataset.loading; };
    next.onerror = () => { delete img.dataset.loading; };
    next.src = `${base}?t=${Date.now()}`;
  });
}
