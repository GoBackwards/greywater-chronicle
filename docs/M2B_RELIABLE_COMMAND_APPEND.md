# M2B Reliable Command Append

## Transaction flow

BEGIN IMMEDIATE
→ load ordered events
→ determine actual revision
→ compare expected revision
→ replay current state
→ validate command
→ append event at actual revision + 1
→ commit

Any failure → rollback

## Outcome table

| Scenario | Actual revision | Expected revision | Mill state | Result | Stored events |
|---|---:|---:|---|---|---:|
| First repair | 0 | 0 | broken | Accept and append revision 1 | 1 |
| Repair again | 1 | 1 | working | `mill_already_working` | 1 |
| Stale client | 1 | 0 | working | `RevisionConflict` | 1 |
| Two simultaneous repairs | 0 initially | 0 each | broken | One succeeds; one conflicts | 1 |
| Database failure | 0 | 0 | broken | Roll back transaction | 0 |
| Retry same command ID | 1 | 0 | working | Return original result without appending | 1 |


## Idempotency decision

`command_id` serves as the idempotency key.

A command fingerprint contains:

- `command_type`
- `actor_id`
- `expected_revision`
- command payload when commands later have payloads

A separate `processed_commands` table records the relationship between an
accepted command and its resulting Chronicle event.

| Column | Purpose |
|---|---|
| `command_id` | Unique identity of one logical command |
| `command_type` | Detects reuse for another command type |
| `actor_id` | Prevents another player from reusing the key |
| `expected_revision` | Confirms the retry is the same request |
| `result_revision` | Locates the previously created event |

## Final transaction order

BEGIN IMMEDIATE
→ look up `command_id`
→ if found with the same fingerprint, return its original event
→ if found with a different fingerprint, reject key reuse
→ load ordered events
→ determine actual revision
→ compare expected revision
→ replay current state
→ validate command
→ append event
→ record processed command
→ commit

Any failure → rollback