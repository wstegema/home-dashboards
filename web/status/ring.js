// One item tile: ring + time + name (+ detail and cover image when there's room).
import { escapeHtml, ringText } from "./format.js";

const SLOTS = 6;

export function tileHtml(item, slot, { withCover = false } = {}) {
  const color = item.status === "failed" ? "var(--failed)" : `var(--slot-${(slot % SLOTS) + 1})`;
  const pct = item.pct ?? 0;
  const cover = withCover && item.image ? `<img class="cover" src="${escapeHtml(item.image)}" alt="">` : "";
  return `<section class="tile" style="--c:${color}"><div class="tile-body">
    <div class="ring">
      <svg viewBox="0 0 100 100" aria-hidden="true">
        <circle class="track" cx="50" cy="50" r="45"/>
        ${pct > 0 ? `<circle class="bar" cx="50" cy="50" r="45" pathLength="100" stroke-dasharray="${pct} 100"/>` : ""}
      </svg>
      <div class="time" data-slot="${slot}"></div>
    </div>
    <div class="info">
      <div class="name">${escapeHtml(item.name)}</div>
      <div class="detail">${escapeHtml(item.detail)}</div>
      ${cover}
    </div>
  </div></section>`;
}

// Called every second: rewrite the time inside each ring.
export function updateTimes(root, items, now) {
  root.querySelectorAll(".time").forEach((el) => {
    const item = items[Number(el.dataset.slot)];
    const secondsLeft = item.ends_at == null ? null : item.ends_at - now;
    const parts = ringText(item, secondsLeft);
    el.dataset.len = parts.join(" ").length > 4 ? "long" : "short";
    el.innerHTML = parts.map((p) => `<span>${p}</span>`).join("");
  });
}
