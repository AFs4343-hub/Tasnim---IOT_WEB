import argparse
import random
import time
from pathlib import Path

import firebase_admin
from firebase_admin import credentials, db


DATABASE_URL = (
    "https://omirisetmonitoring-default-rtdb."
    "asia-southeast1.firebasedatabase.app"
)

CREDENTIAL_PATH = Path(
    "iot/serviceAccountKey.json"
)

DEFAULT_INTERVAL = 5


# ============================================================
# KONDISI DASAR SIMULASI
# ============================================================

NODE_CONFIG = {
    "N0": {
        "ph": 7.20,
        "tds": 210.0,
        "turbidity": 8.0,
        "rssi": -55,
    },

    "N1": {
        "ph": 7.15,
        "tds": 215.0,
        "turbidity": 9.0,
        "rssi": -66,
    },

    "N2": {
        "ph": 7.10,
        "tds": 220.0,
        "turbidity": 10.0,
        "rssi": -74,
    },
}


sequence = {
    "N0": 0,
    "N1": 0,
    "N2": 0,
}


# ============================================================
# FIREBASE
# ============================================================

def initialize_firebase():

    if not CREDENTIAL_PATH.exists():
        raise FileNotFoundError(
            "\nCredential Firebase belum ditemukan:\n"
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


def initialize_sequence():

    for node_id in NODE_CONFIG:

        existing = db.reference(
            f"nodes/{node_id}/latest/sequence"
        ).get()

        try:
            sequence[node_id] = int(existing)
        except (TypeError, ValueError):
            sequence[node_id] = 0


# ============================================================
# GENERATOR DATA NORMAL
# ============================================================

def generate_normal_values(node_id):

    cfg = NODE_CONFIG[node_id]

    return {
        "ph": round(
            random.gauss(
                cfg["ph"],
                0.03
            ),
            2
        ),

        "tds": round(
            random.gauss(
                cfg["tds"],
                3.0
            ),
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
        ),
    }


# ============================================================
# INJEKSI ANOMALI
# ============================================================

def inject_anomaly(
    values,
    node_id,
    anomaly_node,
):

    if anomaly_node is None:
        return values

    if node_id != anomaly_node:
        return values


    # --------------------------------------------------------
    # Ini BUKAN ambang biologis kualitas air.
    #
    # Nilai sengaja dibuat menyimpang untuk menguji apakah
    # pipeline AI-IoT-Web mampu mendeteksi perubahan.
    # --------------------------------------------------------

    values["ph"] = round(
        values["ph"]
        + random.uniform(
            0.9,
            1.3
        ),
        2
    )

    values["tds"] = round(
        values["tds"]
        + random.uniform(
            90,
            130
        ),
        2
    )

    values["turbidity"] = round(
        values["turbidity"]
        + random.uniform(
            18,
            28
        ),
        2
    )

    return values


# ============================================================
# SATU SIKLUS PENGIRIMAN
# ============================================================

def run_cycle(
    anomaly_node=None,
):

    timestamp_ms = int(
        time.time() * 1000
    )

    history_record = {
        "meta": {
            "data_source": "SIMULATION",
            "mode": (
                f"ANOMALI_{anomaly_node}"
                if anomaly_node
                else "NORMAL"
            ),
            "timestamp": timestamp_ms,
        }
    }


    for node_id in NODE_CONFIG:

        sequence[node_id] += 1

        values = generate_normal_values(
            node_id
        )

        values = inject_anomaly(
            values,
            node_id,
            anomaly_node,
        )


        packet = {
            "ph":
                values["ph"],

            "tds":
                values["tds"],

            "turbidity":
                values["turbidity"],

            "timestamp":
                timestamp_ms,

            "sequence":
                sequence[node_id],

            "rssi":
                values["rssi"],
        }


        db.reference(
            f"nodes/{node_id}/latest"
        ).set(packet)


        history_record[
            node_id
        ] = packet


        mode_text = (
            "ANOMALI"
            if node_id == anomaly_node
            else "NORMAL"
        )


        print(
            f"{node_id} | "
            f"{mode_text:<7} | "
            f"seq={packet['sequence']} | "
            f"pH={packet['ph']} | "
            f"TDS={packet['tds']} | "
            f"Turb={packet['turbidity']} | "
            f"RSSI={packet['rssi']} dBm"
        )


    db.reference(
        f"history/{timestamp_ms}"
    ).set(
        history_record
    )


    print(
        f"History saved: {timestamp_ms}"
    )

    print(
        "-" * 85
    )


# ============================================================
# MAIN
# ============================================================

def main():

    parser = argparse.ArgumentParser(
        description=(
            "Simulator IoT TASNIM"
        )
    )


    parser.add_argument(
        "--anomaly",
        choices=[
            "N0",
            "N1",
            "N2",
        ],
        default=None,
        help=(
            "Inject anomali pada node tertentu."
        )
    )


    parser.add_argument(
        "--interval",
        type=float,
        default=DEFAULT_INTERVAL,
        help=(
            "Interval simulasi dalam detik."
        )
    )


    args = parser.parse_args()


    print()
    print(
        "TASNIM IoT Simulator"
    )
    print(
        "===================="
    )


    initialize_firebase()

    initialize_sequence()


    print(
        "Firebase connected."
    )

    print(
        f"Interval demo : "
        f"{args.interval} detik"
    )


    if args.anomaly:

        print(
            f"MODE          : "
            f"ANOMALI_{args.anomaly}"
        )

    else:

        print(
            "MODE          : NORMAL"
        )


    print(
        "Ctrl+C untuk berhenti."
    )

    print()


    try:

        while True:

            run_cycle(
                anomaly_node=args.anomaly
            )

            time.sleep(
                args.interval
            )


    except KeyboardInterrupt:

        print()
        print(
            "Simulator dihentikan."
        )


if __name__ == "__main__":
    main()
