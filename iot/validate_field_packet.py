REQUIRED_FIELDS = {
    "ph",
    "tds",
    "turbidity",
    "timestamp",
    "sequence",
    "rssi",
}


def validate_packet(packet):

    errors = []

    missing = (
        REQUIRED_FIELDS
        - set(packet.keys())
    )

    if missing:
        errors.append(
            "Field hilang: "
            + ", ".join(
                sorted(missing)
            )
        )


    numeric_fields = [
        "ph",
        "tds",
        "turbidity",
        "timestamp",
        "sequence",
        "rssi",
    ]


    for field in numeric_fields:

        if field not in packet:
            continue

        value = packet[field]

        if not isinstance(
            value,
            (int, float)
        ):
            errors.append(
                f"{field} harus berupa angka."
            )


    if (
        isinstance(
            packet.get("timestamp"),
            (int, float)
        )
        and packet["timestamp"] <= 0
    ):
        errors.append(
            "timestamp harus lebih besar dari 0."
        )


    if (
        isinstance(
            packet.get("sequence"),
            (int, float)
        )
        and packet["sequence"] < 0
    ):
        errors.append(
            "sequence tidak boleh negatif."
        )


    return errors


def main():

    demo_packet = {
        "ph": 7.21,
        "tds": 218.4,
        "turbidity": 8.7,
        "timestamp": 1789351500000,
        "sequence": 152,
        "rssi": -63,
    }


    errors = validate_packet(
        demo_packet
    )


    print()
    print(
        "TASNIM Field Packet Validator"
    )
    print(
        "============================="
    )


    if errors:

        print(
            "INVALID"
        )

        for error in errors:
            print(
                f"- {error}"
            )

    else:

        print(
            "VALID"
        )

        print(
            "Paket sesuai Field Data Contract v1."
        )


if __name__ == "__main__":
    main()
