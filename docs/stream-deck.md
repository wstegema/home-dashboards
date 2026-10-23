# Stream Deck keys

The Stream Deck talks only to Home Assistant, through the **Home Assistant** plugin from the Stream Deck store. Home status picks up the result from HA like any other device.

Each key calls an HA service. In the plugin, pick the entity, then the service, and paste the service data where shown. The plugin's exact field names may differ from these; the services and data are what matter.

## Keys

| Key | Service | Entity | Service data |
|---|---|---|---|
| Dishwasher | `timer.start` | `timer.dishwasher` | — (runs 2 h) |
| Dishwasher (long press) | `timer.cancel` | `timer.dishwasher` | — |
| Clear dryer | `input_button.press` | `input_button.clear_dryer` | — |
| Clear finished | `input_button.press` | `input_button.clear_finished` | — |

**Slow cooker** (a folder):

| Key | Service | Entity | Service data |
|---|---|---|---|
| 1h … 6h | `script.slow_cooker_timer` | — | `{"set_minutes": 60}` … `{"set_minutes": 360}` |
| +15m | `script.slow_cooker_timer` | — | `{"add_minutes": 15}` |
| +30m | `script.slow_cooker_timer` | — | `{"add_minutes": 30}` |
| Cancel | `timer.cancel` | `timer.slow_cooker` | — |

Point each slow-cooker key's display at `timer.slow_cooker` to see the time left on the key.

## What each key does on the board

| Press | Board |
|---|---|
| Dishwasher / slow cooker start | A ring counting down |
| Timer runs out | "Done" for 30 minutes |
| Timer cancelled | Disappears; no "Done" |
| +15m / +30m | Adds to what's left; starts from 0 if nothing is running |
| Clear dryer | Removes the dryer's "Done" |
| Clear finished | Removes every Done, Failed, Cooling down and Move to dryer |

## In Home Assistant

| Helper | What |
|---|---|
| `timer.dishwasher` | 2 h. Change the length in Settings → Helpers → Dishwasher. |
| `timer.slow_cooker` | Default 4 h; the keys always set their own length. |
| `script.slow_cooker_timer` | `set_minutes` starts at that length; `add_minutes` adds to what's left. |
| `input_button.clear_dryer`, `input_button.clear_finished` | A press clears finished items on the board. |

To add another timer: create a timer helper in HA, then add `ha_timer("id", "Name", "timer.x")` to `SOURCES` in `server/sources.py`.
