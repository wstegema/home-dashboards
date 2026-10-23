# home-dashboards: requirements

2026-10-15. Distilled from `status-viewer`: the CYD firmware
(`status-viewer/cyd-home-status.yaml`) is the reference design, since that's
where the decisions were tested on real hardware. `ha-dashboard` is dropped.
`Homarr` stays as it is.

## Purpose

Glance at a screen and know what is running in the house, and nothing else.

## What shows

| Source | Shows while | Done when | Time left from | Progress from |
|---|---|---|---|---|
| P1S Color, P1S Mono (Bambu) | `print_status` is running, prepare, pause, slicing or init | `finish`; `failed` shows red "Failed" | `end_time` | `print_progress` |
| Washer, Dryer (LG ThinQ) | `current_status` is anything except power_off, initial or unavailable | `end` (dryer also `wrinkle_care`) | `remaining_time` (it's a finish timestamp, despite the name) | worked out from `total_time` |
| Dishwasher, Slow cooker (HA timer helpers, started from the Stream Deck) | timer is active or paused | runs out (cancelling shows nothing) | `finishes_at` | worked out from `duration` |
| Calendar events (later) | starting soon | started | event start | none |
| Unraid parity check / alerts (later) | running or active | finished or cleared | to be decided | to be decided |

Later sources need Home Assistant integrations that aren't working yet:
- **Google Calendar:** not added to HA.
- **Unraid Management Agent:** installed, but fails with 401. The integration needs the agent's API token.

Entity IDs verified against live HA on 2026-10-14 are in the CYD YAML.

## Rules

- An item shows while it runs.
- After it is **seen** finishing (a device that had already finished before the server started shows nothing):
  - **Printers:** "Cooling down" (bed temperature in the ring) until the bed is at or below 25 °C, then "Done" for 30 minutes. If the room is too warm to get there, "Done" after 3 hours anyway. A failed print shows "Failed" for 30 minutes right away.
  - **Washer:** "Move to dryer" until the dryer *starts* a cycle (not if it was still running the previous load) or the washer starts again. No time limit.
  - **Dryer:** "Done" for 30 minutes. Showing it until the door opens isn't possible: there's no door sensor, and LG machines switch themselves off ~30 s after finishing.
  - **Timers:** "Done" for 30 minutes.
- Switching off (power_off) never clears a finished state.
- **Clear keys** (Stream Deck): "Clear dryer" removes the dryer's Done; "Clear finished" removes every finished item.
- Order: things that need you first (done, failed, move to dryer; newest first), then cooling, then running by soonest finish.
- Nothing running: a clock and the date.

## Display

- **Time left** in whole minutes, rounded up: `44m`, `2h 05m`. No seconds.
- **One ring per item**, filled by progress, with the time inside and the name underneath. The time is the most important element; drop everything else first when space runs out.
- **Color by position** on screen, not by device: orange, yellow, green, cyan, pink, purple. Failed is red.
- **High contrast:** black background, white bold text, saturated colors, thick rings. The CYD panel washes out greys and thin text.
- **Layouts by number of items:**

  | Items | Layout |
  |---|---|
  | 0 | Clock and date |
  | 1 | One big ring (cover image beside it for printers) |
  | 2 | Two rings: stacked on 4:3, side by side on 16:9 |
  | 3–4 | 2×2 grid |
  | 5–6 | 3×2 grid |
  | 7+ | Pages of 6, rotating every 8 s |

## Screens

| Screen | Size | How |
|---|---|---|
| CYD 2.8" ESP32 | 320×240 | Native ESPHome firmware. It already does all of the above; it gets updated last, once the design stops changing. |
| Raspberry Pi + HDMI | 1920×1080 | Kiosk browser. No login after reboot. |
| Homarr | widget size | iframe widget. Homarr stays the launcher and homelab dashboard. |
| Any browser | any | |

## Platform

- **One container on Unraid.** It may host more dashboards later; this is the first.
- **Data from Home Assistant only,** over one connection that all screens share.
- **One long-lived HA token** in the container's `.env`. Screens never log in or see it.
- **Testing:**
  - **Demo scenarios:** 0–6 items, plus done and failed, so every layout can be checked with nothing running.
  - **Preview sheet:** shows every scenario at 320×240 and 1920×1080. I screenshot it to check layouts without needing you.

## Not in scope

- Controlling devices (that was ha-dashboard).
- Homelab dashboards (Homarr).
- A browser on the CYD.

## Open decision: stack

React + TypeScript was chosen to reuse ha-dashboard's code. With ha-dashboard
dropped, that reason is gone.

- **Recommended: Python server + plain HTML/CSS/JS.** The prototype in
  `status-viewer/dashboards` already works in this stack: HA connection, demo
  scenarios, preview sheet, Dockerfile. It needs no build step, and one page
  doesn't need a framework.
- **React + TypeScript:** type checking and components. It adds a build step
  and Node in the container.
