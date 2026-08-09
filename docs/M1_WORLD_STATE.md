# M1 World State

## Scope

This milestone represents only whether Greywater's mill is broken or working.

## Canonical state

| Field | Type | Allowed values | Initial value | Invariant | Why required |
|---|---|---|---|---|---|
| `mill_status` | `MillStatus` enum | `broken`, `working` | `broken` | Must always contain exactly one allowed value and may change only through an accepted Chronicle event | It is the authoritative source of truth for the mill's condition |

## Derived presentation

| Player-facing result | Derivation rule |
|---|---|
| Mill sprite | If `mill_status` is `broken`, show the broken sprite; if `working`, show the repaired sprite |
| Miller dialogue | If `broken`, explain that the wheel is damaged; if `working`, acknowledge that the mill operates again |
| Flour availability message | If `broken`, say flour is unavailable; if `working`, say flour is available |

## State transition

| Current state | Event | Next state |
|---|---|---|
| `broken` | `MillRepaired` | `working` |


## Explicitly excluded

- Player inventory
- Timber consumption
- Flour quantity
- Quest framework
- World revision
- Database persistence
- NPC memory
- AI dialogue
- Multiplayer presence


## Decision

I chose an enum instead of a Boolean or free-form string because:
- It is domain language, restricted values, extendable
- Presentation values should be derived to avoid consistency problems