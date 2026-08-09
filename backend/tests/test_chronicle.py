from dataclasses import FrozenInstanceError
import pytest
from app.chronicle.models import (
    MillRepaired,
    MillStatus,
    RepairMill,
    WorldState,
)
from app.chronicle.reducer import reduce_world, replay
from app.chronicle.handlers import CommandRejected, handle_repair_mill

def test_new_world_starts_with_broken_mill():
    state = WorldState()

    assert state.mill_status is MillStatus.BROKEN


def test_mill_status_contains_only_designed_values():
    values = {status.value for status in MillStatus}

    assert values == {"broken", "working"}

def test_world_state_is_immutable():
    state = WorldState()

    with pytest.raises(FrozenInstanceError):
        setattr(state, "mill_status", MillStatus.WORKING)

    assert state.mill_status is MillStatus.BROKEN

def test_mill_repaired_event_makes_mill_working():
    initial = WorldState()
    event = MillRepaired(actor_id="player-a")

    result = reduce_world(initial, event)

    assert result.mill_status is MillStatus.WORKING


def test_reducer_does_not_mutate_input_state():
    initial = WorldState()
    event = MillRepaired(actor_id="player-a")

    result = reduce_world(initial, event)

    assert initial.mill_status is MillStatus.BROKEN
    assert result.mill_status is MillStatus.WORKING
    assert result is not initial

def test_replay_without_events_returns_initial_state():
    initial = WorldState()

    result = replay([], initial_state=initial)
    assert result == initial

def test_replay_without_initial_state_creates_default_world():
    result = replay([])

    assert result == WorldState()
    assert result.mill_status is MillStatus.BROKEN


def test_replaying_same_events_produces_equal_state():
    events = [MillRepaired(actor_id="player-a")]

    first_result = replay(events)
    second_result = replay(events)

    assert first_result == second_result

def test_repair_command_emits_event_when_mill_is_broken():
    state = WorldState()

    event = handle_repair_mill(
        state=state,
        command=RepairMill(),
        actor_id="player-a",
    )

    assert isinstance(event, MillRepaired)
    assert event.actor_id == "player-a"
    assert state.mill_status is MillStatus.BROKEN

def test_repair_command_is_rejected_when_mill_is_working():
    state = WorldState(mill_status=MillStatus.WORKING)

    with pytest.raises(CommandRejected, match="mill_already_working"):
        handle_repair_mill(
            state=state,
            command=RepairMill(),
            actor_id="player-b",
        )

def test_mill_repaired_records_actor_and_is_immutable():
    event = MillRepaired(actor_id="player-a")

    assert event.actor_id == "player-a"

    with pytest.raises(FrozenInstanceError):
        setattr(event, "actor_id", "player-b")