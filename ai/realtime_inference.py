import argparse
import time
from pathlib import Path

import firebase_admin
import joblib
import pandas as pd

from firebase_admin import credentials, db

from ai.predict import predict_latest


DATABASE_URL = (
    "https://omirisetmonitoring-default-rtdb."
    "asia-southeast1.firebasedatabase.app"
)

CREDENTIAL_PATH = Path(
    "iot/serviceAccountKey.json"
)

MODEL_PATH = Path(
    "ai/models/tasnim_ai_bundle.joblib"
)

HISTORY_LIMIT = 12
POLL_SECONDS = 5

# Model prototype dilatih dari data simulasi
# dengan interval pengukuran 5 menit.
DEMO_INTERVAL_MINUTES = 5

NODES = ["N0", "N1", "N2"]
PARAMETERS = ["ph", "tds", "turbidity"]


def initialize_firebase():

    if not CREDENTIAL_PATH.exists():
        raise FileNotFoundError(
            "Credential Firebase tidak ditemukan: "
            f"{CREDENTIAL_PATH}"
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


def load_model():

    if not MODEL_PATH.exists():
        raise FileNotFoundError(
            "Model AI tidak ditemukan: "
            f"{MODEL_PATH}"
        )

    return joblib.load(
        MODEL_PATH
    )


def load_recent_history():

    data = (
        db.reference("history")
        .order_by_key()
        .limit_to_last(HISTORY_LIMIT)
        .get()
    )

    if not data:
        return None, None, None

    rows = []

    for key, slot in data.items():

        if not isinstance(slot, dict):
            continue

        try:
            source_timestamp = int(key)
        except (TypeError, ValueError):
            continue

        # Untuk analisis spasial, satu slot harus
        # memiliki N0, N1, dan N2.
        if not all(
            node in slot
            for node in NODES
        ):
            continue

        row = {
            "source_timestamp_ms":
                source_timestamp,

            "session_id":
                "LIVE"
        }

        valid = True

        for node in NODES:

            node_data = slot.get(
                node,
                {}
            )

            for parameter in PARAMETERS:

                value = node_data.get(
                    parameter
                )

                if value is None:
                    valid = False
                    break

                row[
                    f"{parameter}_{node}"
                ] = float(value)

            if not valid:
                break

        if valid:
            rows.append(row)


    if len(rows) < 2:
        return None, None, None


    rows = sorted(
        rows,
        key=lambda item:
            item["source_timestamp_ms"]
    )

    df = pd.DataFrame(rows)

    actual_time = pd.to_datetime(
        df["source_timestamp_ms"],
        unit="ms"
    )

    # -------------------------------------------------
    # DETEKSI MODE DEMO
    # -------------------------------------------------
    # Simulator berjalan tiap 5 detik agar mudah dilihat.
    # Model prototype dilatih dengan interval 5 menit.
    #
    # Jika data datang terlalu cepat, waktu fitur temporal
    # dinormalisasi menjadi 5 menit.
    #
    # Data alat asli 5-10 menit nanti memakai waktu aktual.
    # -------------------------------------------------

    intervals = (
        actual_time
        .diff()
        .dt.total_seconds()
        .dropna()
    )

    if (
        not intervals.empty
        and intervals.median() < 60
    ):

        latest_actual = (
            actual_time.iloc[-1]
        )

        count = len(df)

        start_time = (
            latest_actual
            - pd.Timedelta(
                minutes=(
                    DEMO_INTERVAL_MINUTES
                    * (count - 1)
                )
            )
        )

        df["timestamp"] = [
            start_time
            + pd.Timedelta(
                minutes=(
                    DEMO_INTERVAL_MINUTES
                    * index
                )
            )
            for index in range(count)
        ]

        time_mode = (
            "DEMO_NORMALIZED_5_MIN"
        )

    else:

        df["timestamp"] = (
            actual_time
        )

        time_mode = (
            "ACTUAL_TIMESTAMP"
        )


    latest_source_timestamp = int(
        df[
            "source_timestamp_ms"
        ].iloc[-1]
    )

    return (
        df,
        latest_source_timestamp,
        time_mode
    )


def run_inference(
    model_bundle
):

    (
        input_df,
        source_timestamp,
        time_mode
    ) = load_recent_history()


    if input_df is None:
        print(
            "Menunggu minimal 2 slot "
            "history lengkap N0/N1/N2..."
        )

        return None, None


    result = predict_latest(
        input_df,
        model_bundle
    )


    # Firebase RTDB lebih aman memakai string
    # daripada None untuk lokasi NORMAL.
    result["location"] = (
        result.get("location")
        or "-"
    )

    result[
        "source_timestamp_ms"
    ] = source_timestamp

    result[
        "inference_timestamp_ms"
    ] = int(
        time.time() * 1000
    )

    result[
        "model_stage"
    ] = "PROTOTYPE_SIMULATION"

    result[
        "model_version"
    ] = "prototype-v1"

    result[
        "data_source"
    ] = "SIMULATION"

    result[
        "time_mode"
    ] = time_mode


    # Hasil terbaru untuk dashboard realtime
    db.reference(
        "analysis/latest"
    ).set(result)


    # Arsip hasil AI pada history pengukuran yang sama
    db.reference(
        f"history/{source_timestamp}/analysis"
    ).set(result)


    rf = result[
        "random_forest"
    ]

    print()
    print(
        "AI RESULT"
    )
    print(
        "---------"
    )
    print(
        f"Status     : "
        f"{result['status']}"
    )
    print(
        f"Lokasi     : "
        f"{result['location']}"
    )
    print(
        f"RF         : "
        f"{rf['prediction']}"
    )
    print(
        f"Confidence : "
        f"{rf['confidence'] * 100:.1f}%"
    )
    print(
        f"IF anomaly : "
        f"{result['isolation_forest']['is_anomaly']}"
    )
    print(
        f"Dominan    : "
        f"{result['dominant_zscore']['parameter']} "
        f"{result['dominant_zscore']['node']}"
    )
    print(
        f"Z-score    : "
        f"{result['dominant_zscore']['zscore']:.2f}"
    )
    print(
        f"Time mode  : "
        f"{time_mode}"
    )
    print(
        "Saved → /analysis/latest"
    )

    return (
        result,
        source_timestamp
    )


def main():

    parser = argparse.ArgumentParser(
        description=(
            "Realtime AI inference TASNIM"
        )
    )

    parser.add_argument(
        "--once",
        action="store_true",
        help=(
            "Jalankan prediksi sekali "
            "lalu berhenti."
        )
    )

    args = parser.parse_args()


    print()
    print(
        "TASNIM Realtime AI"
    )
    print(
        "=================="
    )

    initialize_firebase()

    print(
        "Firebase connected."
    )

    model_bundle = (
        load_model()
    )

    print(
        "Model loaded."
    )

    last_processed = None


    try:

        while True:

            (
                result,
                source_timestamp
            ) = run_inference(
                model_bundle
            )


            if (
                source_timestamp
                is not None
                and source_timestamp
                != last_processed
            ):
                last_processed = (
                    source_timestamp
                )


            if args.once:
                break


            time.sleep(
                POLL_SECONDS
            )


    except KeyboardInterrupt:

        print()
        print(
            "Realtime AI dihentikan."
        )


if __name__ == "__main__":
    main()
