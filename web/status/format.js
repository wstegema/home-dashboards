// Text shown inside a ring.

// Whole minutes, rounded up: "44m", or ["2h", "05m"] as two parts so small
// rings can stack them. Status words replace the time once an item finishes.
export function ringText(item, secondsLeft) {
  if (item.status === "done") return ["Done"];
  if (item.status === "failed") return ["Failed"];
  if (secondsLeft == null) return ["--"];
  const mins = Math.ceil(Math.max(0, secondsLeft) / 60);
  if (mins < 60) return [`${mins}m`];
  return [`${Math.floor(mins / 60)}h`, `${String(mins % 60).padStart(2, "0")}m`];
}

export const escapeHtml = (s) =>
  String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
