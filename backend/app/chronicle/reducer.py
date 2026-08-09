from dataclasses import replace

from app.chronicle.models import MillRepaired, MillStatus, WorldState

def reduce_world(
    state: WorldState,
    event: MillRepaired,
) -> WorldState:
    """Return a new world state produced by one accepted event."""
    if isinstance(event, MillRepaired):
        return replace(
            state,
            mill_status=MillStatus.WORKING,
        )

    raise TypeError(f"Unsupported event: {type(event).__name__}")


def replay(
    events: list[MillRepaired],
    initial_state: WorldState | None = None,
) -> WorldState:
    """Reconstruct world state by applying accepted events in order."""
    state = initial_state if initial_state is not None else WorldState()

    for event in events:
        state = reduce_world(state, event)

    return state


