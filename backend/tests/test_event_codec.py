import pytest

from app.chronicle.codec import EventCodecError, decode_event, encode_event
from app.chronicle.models import MillRepaired



def test_encode_mill_repaired_uses_stable_versioned_shape():
    event = MillRepaired(actor_id="player-a")

    encoded = encode_event(event)

    assert encoded == {
        "event_type": "mill_repaired",
        "schema_version": 1,
        "payload": {
            "actor_id": "player-a",
        },
    }

def test_decode_v1_mill_repaired_reconstructs_domain_event():
    stored_data = {
        "event_type": "mill_repaired",
        "schema_version": 1,
        "payload": {
            "actor_id": "player-a",
        },
    }

    event = decode_event(stored_data)

    assert event == MillRepaired(actor_id="player-a")


def test_decode_rejects_unknown_event_type():
    stored_data = {
        "event_type": "dragon_awakened",
        "schema_version": 1,
        "payload": {
            "actor_id": "player-a",
        },
    }

    with pytest.raises(EventCodecError, match="unsupported_event_type"):
        decode_event(stored_data)


def test_decode_rejects_unsupported_schema_version():
    stored_data = {
        "event_type": "mill_repaired",
        "schema_version": 2,
        "payload": {
            "actor_id": "player-a",
        },
    }

    with pytest.raises(EventCodecError, match="unsupported_schema_version"):
        decode_event(stored_data)

def test_decode_rejects_non_mapping_payload():
    stored_data = {
        "event_type": "mill_repaired",
        "schema_version": 1,
        "payload": "not-a-mapping",
    }

    with pytest.raises(EventCodecError, match="invalid_event_payload"):
        decode_event(stored_data)

def test_decode_rejects_missing_actor_id():
    stored_data = {
        "event_type": "mill_repaired",
        "schema_version": 1,
        "payload": {},
    }

    with pytest.raises(EventCodecError, match="invalid_actor_id"):
        decode_event(stored_data)

def test_decode_rejects_non_string_actor_id():
    stored_data = {
        "event_type": "mill_repaired",
        "schema_version": 1,
        "payload": {
            "actor_id": 123,
        },
    }

    with pytest.raises(EventCodecError, match="invalid_actor_id"):
        decode_event(stored_data)

def test_mill_repaired_round_trip_preserves_event():
    original = MillRepaired(actor_id="player-a")

    restored = decode_event(encode_event(original))

    assert restored == original
    assert restored is not original