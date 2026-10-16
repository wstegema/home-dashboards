// Nothing running: the time and date, in Home Assistant's time zone.

export const clockHtml = () => `<div class="clock"></div><div class="date"></div>`;

export function updateClock(root, now, timeZone) {
  const clock = root.querySelector(".clock");
  if (!clock) return;
  const t = new Date(now * 1000);
  const tz = timeZone || undefined;
  const parts = new Intl.DateTimeFormat("en-US", { hour: "numeric", minute: "2-digit", timeZone: tz }).formatToParts(t);
  const hm = parts.filter((p) => p.type !== "dayPeriod").map((p) => p.value).join("").trim();
  const ampm = parts.find((p) => p.type === "dayPeriod")?.value ?? "";
  clock.innerHTML = `${hm}<small>${ampm}</small>`;
  root.querySelector(".date").textContent =
    new Intl.DateTimeFormat("en-US", { weekday: "long", month: "long", day: "numeric", timeZone: tz }).format(t);
}
