// One item tile: ring + time + name (+ detail when there's room). Prints show their
// thumbnail inside the ring.
// The detail view adds percent, finish time, "finished … ago", and a media
// column with the printer's live camera.
import { ago, clockTime, escapeHtml, ringText } from "./format.js";

const SLOTS = 6;

export function tileHtml(item, slot, { detail = false, withCamera = false, tz = null } = {}) {
  const color = item.status === "failed" ? "var(--failed)" : `var(--slot-${(slot % SLOTS) + 1})`;
  const pct = item.pct ?? 0;
  // Running prints: the thumbnail sits inside the ring, which becomes its progress border.
  const thumb = item.image && item.status === "running" ? `<img class="thumb" src="${escapeHtml(item.image)}" alt="">` : "";
  return `<section class="tile" data-status="${item.status}" style="--c:${color}"><div class="tile-body">
    <div class="ring${thumb ? " has-thumb" : ""}">
      ${thumb}
      <svg viewBox="0 0 100 100" aria-hidden="true">
        <circle class="track" cx="50" cy="50" r="45"/>
        ${pct > 0 ? `<circle class="bar" cx="50" cy="50" r="45" pathLength="100" stroke-dasharray="${pct} 100"/>` : ""}
      </svg>
      <div class="time" data-slot="${slot}"></div>
    </div>
    <div class="info">
      <div class="name">${escapeHtml(item.name)}</div>
      <div class="detail">${escapeHtml(item.detail)}</div>
      ${detail ? factsHtml(item, slot, tz) : ""}
    </div>
    ${detail ? mediaHtml(item, withCamera) : ""}
  </div></section>`;
}

// Detail view only: the printer's live camera beside the facts.
function mediaHtml(item, withCamera) {
  if (!withCamera || !item.camera) return "";
  return `<div class="media"><img class="live" data-live src="${escapeHtml(item.camera)}" alt=""></div>`;
}

// Detail view only: the facts under the name.
function factsHtml(item, slot, tz) {
  const facts = [];
  if (item.status === "running") {
    if (item.pct != null) facts.push(`<span class="fact-big">${item.pct}%</span>`);
    if (item.ends_at != null) facts.push(`<span>Ends ${clockTime(item.ends_at, tz)}</span>`);
  } else if (item.status === "cooling") {
    if (item.temp != null) facts.push(`<span class="fact-big">${item.temp}°C</span>`);
    facts.push(`<span>Finished ${clockTime(item.done_at, tz)}</span>`);
  } else if (item.done_at != null) {
    facts.push(`<span>${item.status === "failed" ? "Failed" : "Finished"} ${clockTime(item.done_at, tz)}</span>`);
    facts.push(`<span class="ago" data-slot="${slot}"></span>`);
  }
  return `<div class="facts">${facts.join("")}</div>`;
}

// Called every second: rewrite the time inside each ring (and "… ago" lines).
export function updateTimes(root, items, now) {
  root.querySelectorAll(".time").forEach((el) => {
    const item = items[Number(el.dataset.slot)];
    const secondsLeft = item.ends_at == null ? null : item.ends_at - now;
    const parts = ringText(item, secondsLeft);
    el.dataset.len = parts.join(" ").length > 4 ? "long" : "short";
    el.innerHTML = parts.map((p) => `<span>${p}</span>`).join("");
  });
  root.querySelectorAll(".ago").forEach((el) => {
    el.textContent = ago(now - items[Number(el.dataset.slot)].done_at);
  });
}
