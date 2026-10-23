// Text shown inside a ring, and the extra lines of the detail view.

// Whole minutes, rounded up: "44m", or ["2h", "05m"] as two parts so small
// rings can stack them. Once an item finishes: its bed temperature while it
// cools ("41°"), "Move" while the washer waits for the dryer, then a status word.
export function ringText(item, secondsLeft) {
  if (item.status === "done") return ["Done"];
  if (item.status === "failed") return ["Failed"];
  if (item.status === "waiting") return ["Move"];
  if (item.status === "cooling") return [item.temp == null ? "Cool" : `${item.temp}°`];
  if (secondsLeft == null) return ["--"];
  const mins = Math.ceil(Math.max(0, secondsLeft) / 60);
  if (mins < 60) return [`${mins}m`];
  return [`${Math.floor(mins / 60)}h`, `${String(mins % 60).padStart(2, "0")}m`];
}

// "4:12 PM" in Home Assistant's time zone.
export const clockTime = (ts, timeZone) =>
  new Intl.DateTimeFormat("en-US", { hour: "numeric", minute: "2-digit", timeZone: timeZone || undefined })
    .format(new Date(ts * 1000));

// "just now", "12m ago", "1h 05m ago".
export function ago(seconds) {
  const mins = Math.floor(Math.max(0, seconds) / 60);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  return `${Math.floor(mins / 60)}h ${String(mins % 60).padStart(2, "0")}m ago`;
}

export const escapeHtml = (s) =>
  String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
