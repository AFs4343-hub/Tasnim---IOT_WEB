from field_contract import (
    SLOT_MS,
    canonical_slot_ms,
    is_ai_analyzable,
    validate_location,
    validate_node_id,
    validate_storage_packet,
)


def test():
    complete = {
        "ph": 7.2,
        "tds": 218.4,
        "turbidity": 8.7,
        "timestamp": 1789351501000,
        "sequence": 10,
        "rssi": -63,
    }

    missing_turb = {
        "ph": 7.2,
        "tds": 218.4,
        "timestamp": 1789351501000,
        "sequence": 10,
        "rssi": -63,
    }

    assert SLOT_MS == 300000

    assert validate_node_id("N0")
    assert validate_node_id("N1")
    assert validate_node_id("N2")
    assert not validate_node_id("N3")

    assert validate_storage_packet(complete) == []
    assert is_ai_analyzable(complete)

    assert validate_storage_packet(missing_turb) == []
    assert not is_ai_analyzable(missing_turb)

    assert canonical_slot_ms(1789351501000) % 300000 == 0

    assert validate_storage_packet({
        "ph": -1,
        "tds": 100,
        "timestamp": 1789351501000,
    })

    assert validate_storage_packet({
        "ph": 7,
        "tds": -10,
        "timestamp": 1789351501000,
    })

    assert validate_storage_packet({
        "ph": 7,
        "tds": 100,
        "timestamp": 0,
    })

    assert validate_location({
        "latitude": 0.5,
        "longitude": 123.1,
        "captured_timestamp": 1789351501000,
    }) == []

    assert validate_location({
        "latitude": 100,
        "longitude": 123,
    })

    print("[PASS] FIELD contract unit test")


if __name__ == "__main__":
    test()
