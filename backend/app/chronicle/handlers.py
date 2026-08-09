from app.chronicle.models import (
    MillRepaired,
    MillStatus,
    RepairMill,
    WorldState,
)


class CommandRejected(Exception):
    pass


def handle_repair_mill(
    state: WorldState,
    command: RepairMill,
    actor_id: str,
) -> MillRepaired:
    if state.mill_status is MillStatus.WORKING:
        raise CommandRejected("mill_already_working")

    return MillRepaired(actor_id=actor_id)