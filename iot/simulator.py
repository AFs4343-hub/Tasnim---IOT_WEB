import random
import time
from pathlib import Path

import firebase_admin
from firebase_admin import credentials, db


DATABASE_URL = (
    "https://omirisetmonitoring-default-rtdb."
    "asia-southeast1.firebasedatabase.app"
)

CREDENTIAL_PATH = Path("iot/serviceAccountKey.json")

# Mode demo: 5 detik.
# Alat nyata nanti sekitar 5 menit.
INTERVAL_SECONDS = 5


NODE_CONFIG = {
    "N0": {
        "ph": 7.20,
        "tds": 210.0,
        "turbidity": 8.0,
        "rssi": -55
    },
    "N1": {
        "ph": 7.15,
        "tds": 215.0,
        "turbidity": 9.0,
        "rssi": -66
    },
    "N2": {
        "ph": 7.10,
        "tds": 220.0,
        "turbidity": 10.0,
        "rssi": -74
    }
}


sequence = {
    "N0": 0,
    "N1": 0,
    "N2": 0
}


def initialize_firebase():
    if not CREDENTIAL_PATH.exists():
        raise FileNotFoundError(
            "\nCredential Firebase belum ada.\n"
            "Letakkan file di:\n"
            "iot/serviceAccountKey.json\n"
        )

    cred = credentials.Certificate(
        str(CREDENTIAL_PATH)
    )

    firebase_admin.initialize_app(
        cred,
        {
            "databaseURL": DATABASE_URL
        }
    )


def generate_values(node_id):
    cfg = NODE_CONFIG[node_id]

    return {
        "ph": round(
            random.gauss(cfg["ph"], 0.03),
            2
        ),
        "tds": round(
            random.gauss(cfg["tds"], 3.0),
            2
        ),
        "turbidity": round(
            max(
                0,
                random.gauss(
                    cfg["turbidity"],
                    0.5
                )
            ),
            2
        ),
        "rssi": round(
            random.gauss(
                cfg["rssi"],
                2
            )
        )
    }


def run_cycle():
    timestamp_ms = int(
        time.time() * 1000
    )

    history_record = {}

    for node_id in NODE_CONFIG:

        sequence[node_id] += 1

        values = generate_values(
            node_id
        )

        packet = {
            "ph": values["ph"],
            "tds": values["tds"],
            "turbidity": values["turbidity"],
            "timestamp": timestamp_ms,
            "sequence": sequence[node_id],
            "rssi": values["rssi"]
        }

        # Data terbaru
        db.reference(
            f"nodes/{node_id}/latest"
        ).set(packet)

        # Data histori
        history_record[node_id] = packet

        print(
            f"{node_id} | "
            f"seq={packet['sequence']} | "
            f"pH={packet['ph']} | "
            f"TDS={packet['tds']} | "
            f"Turb={packet['turbidity']} | "
            f"RSSI={packet['rssi']} dBm"
        )

    # Ketiga node disimpan pada timestamp yang sama
    db.reference(
        f"history/{timestamp_ms}"
    ).set(history_record)

    print(
        f"History saved: {timestamp_ms}"
    )

    print("-" * 70)


def main():
    print()
    print("TASNIM IoT Simulator")
    print("====================")

    initialize_firebase()

    print("Firebase connected.")
    print(
        f"Interval demo: {INTERVAL_SECONDS} detik"
    )
    print("Ctrl+C untuk berhenti.")
    print()

    try:
        while True:
            run_cycle()

            time.sleep(
                INTERVAL_SECONDS
            )

    except KeyboardInterrupt:
        print()
        print("Simulator dihentikan.")


if __name__ == "__main__":
    main()
