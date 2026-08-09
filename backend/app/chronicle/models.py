from dataclasses import dataclass
from enum import StrEnum

class MillStatus(StrEnum):
    BROKEN = "broken"
    WORKING = "working"

@dataclass(frozen=True)
class WorldState:
    mill_status: MillStatus = MillStatus.BROKEN

@dataclass(frozen=True)
class MillRepaired:
    actor_id: str

@dataclass(frozen=True)
class RepairMill:
    pass