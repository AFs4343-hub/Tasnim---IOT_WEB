import argparse
import json
import time
from pathlib import Path

import firebase_admin
import joblib
import pandas as pd

from firebase_admin import credentials, db

from ai.predict import predict_latest
from ai.check_ai_readiness import audit_slot, WARNING_FLAGS, INFO_FLAGS


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

CONFIG_PATH = Path("tasnim.config.json")

with CONFIG_PATH.open() as config_file:
    TASNIM_CONFIG = json.load(config_file)

DATA_ROOT = TASNIM_CONFIG["activeDataRoot"]
DATA_MODE = TASNIM_CONFIG["mode"]
DRY_RUN = False

# Model prototype dilatih dari data simulasi
# dengan interval pengukuran 5 menit.
DEMO_INTERVAL_MINUTES = 5

NODES = ["N0", "N1", "N2"]
PARAMETERS = ["ph", "tds", "turbidity"]

# Root yang history-nya berupa slot 5 menit dari alat (bukan simulasi).
GATED_ROOTS = ("real_test", "field", "hardware_test")

# Data alat tidak punya meta.session_id. Slot berurutan dianggap satu sesi
# pengukuran selama jedanya <= 15 menit; lebih dari itu = sesi baru
# (mis. hari berikutnya), agar rate-of-change tidak melompati malam.
HARDWARE_SESSION_GAP_MS = 15 * 60 * 1000

_REPORTED_SKIPS = {}

DATA_SOURCE_LABELS = {
    "simulation": "SIMULATION",
    "real_test": "REAL_TEST",
    "field": "FIELD",
    "hardware_test": "HARDWARE_TEST",
}


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



# === TASNIM SENSOR VALIDATION ===
def is_valid_sensor_value(sensor_name, value):
    """
    Validasi fisik dasar sebelum data masuk AI.

    Catatan:
    - Ini bukan batas kualitas air budidaya.
    - Ini hanya menolak nilai sensor yang secara fisik
      mustahil / jelas rusak.
    """
    try:
        value = float(value)
    except (TypeError, ValueError):
        return False

    import math

    if not math.isfinite(value):
        return False

    if sensor_name == "ph":
        return 0.0 <= value <= 14.0

    if sensor_name == "tds":
        return value >= 0.0

    if sensor_name == "turbidity":
        return value >= 0.0

    return False


def is_valid_node_packet(node):
    if not isinstance(node, dict):
        return False

    required = (
        "ph",
        "tds",
        "turbidity",
    )

    for sensor in required:
        if sensor not in node:
            return False

        if not is_valid_sensor_value(
            sensor,
            node.get(sensor)
        ):
            return False

    return True


def load_recent_history(
    limit=HISTORY_LIMIT,
):

    query = (
        db.reference(f"{DATA_ROOT}/history")
        .order_by_key()
    )

    # Realtime memakai window kecil.
    # Recovery startup dapat memakai limit=None
    # untuk membaca seluruh history.
    if limit is not None:
        query = query.limit_to_last(
            limit
        )

    data = query.get()

    return history_to_frame(
        data,
        DATA_ROOT,
    )


def history_to_frame(
    data,
    data_root,
    verbose=True,
):
    """Ubah dict history Firebase menjadi DataFrame input model.

    Fungsi murni (tanpa Firebase) agar bisa dipakai juga untuk analisis
    CSV microSD secara offline. Return (df, pending_timestamps, time_mode)
    atau (None, None, None) jika slot valid < 2.
    """

    if not data or not isinstance(data, dict):
        return None, None, None

    rows = []

    for key, slot in data.items():

        if not isinstance(slot, dict):
            continue

        try:
            source_timestamp = int(key)
        except (TypeError, ValueError):
            continue

        # Validasi sensor dan kualitas paket sebelum AI.
        # SIMULATION tetap memakai perilaku sebelumnya.
        if data_root in GATED_ROOTS:
            # Flag peringatan (TDS 0 / turbiditas 0) tidak membatalkan
            # analisis untuk data alat; tetap tampil di website.
            allowed = (
                INFO_FLAGS | WARNING_FLAGS
                if data_root == "hardware_test"
                else INFO_FLAGS
            )
            reasons = audit_slot(key, slot, allowed_flags=allowed)

            if reasons:
                message = (
                    f"[AI GATE SKIP] {data_root}/{key}: "
                    + "; ".join(reasons)
                )
                # Loop realtime membaca ulang tiap 5 detik; cetak alasan
                # yang sama untuk slot yang sama cukup sekali.
                if verbose and _REPORTED_SKIPS.get(key) != message:
                    _REPORTED_SKIPS[key] = message
                    print(message)
                continue

        # Untuk analisis spasial, satu slot harus
        # memiliki N0, N1, dan N2.
        if not all(
            node in slot
            for node in NODES
        ):
            continue

        meta = slot.get(
            "meta",
            {}
        )

        if not isinstance(meta, dict):
            meta = {}


        session_id = meta.get(
            "session_id"
        )

        # History lama belum mempunyai session_id.
        # Dibuat unik per timestamp agar data legacy
        # tidak dianggap berasal dari sesi yang sama.
        if not session_id:
            session_id = (
                f"LEGACY_{source_timestamp}"
            )


        row = {
            "source_timestamp_ms":
                source_timestamp,

            "session_id":
                str(session_id),

            # True jika record ini sudah pernah
            # dianalisis dan memiliki /analysis.
            "has_analysis":
                isinstance(
                    slot.get("analysis"),
                    dict
                )
        }

        valid = True

        # Reject physically invalid sensor packets before AI
        if not all(
            is_valid_node_packet(
                slot.get(node)
            )
            for node in NODES
        ):
            continue


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

    if data_root == "hardware_test":
        assign_gap_sessions(rows)

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


    pending_timestamps = (
        df.loc[
            ~df["has_analysis"],
            "source_timestamp_ms"
        ]
        .astype(int)
        .tolist()
    )

    return (
        df,
        pending_timestamps,
        time_mode
    )



def assign_gap_sessions(rows):
    """Beri session_id berdasarkan jeda antar slot (data alat)."""

    session_id = None
    previous = None

    for row in rows:
        timestamp = row["source_timestamp_ms"]

        if (
            previous is None
            or timestamp - previous > HARDWARE_SESSION_GAP_MS
        ):
            session_id = f"HW_{timestamp}"

        row["session_id"] = session_id
        previous = timestamp

    return rows


def build_analysis_result(
    input_df,
    target_timestamp,
    time_mode,
    model_bundle,
    data_root,
    inference_timestamp_ms=None,
):
    """Prediksi untuk satu slot tanpa menulis ke mana pun."""

    target_df = (
        input_df[
            input_df["source_timestamp_ms"]
            <= target_timestamp
        ]
        .copy()
    )

    if target_df.empty:
        return None

    result = predict_latest(
        target_df,
        model_bundle
    )

    result["location"] = (
        result.get("location")
        or "-"
    )

    result["source_timestamp_ms"] = int(
        target_timestamp
    )

    result["inference_timestamp_ms"] = int(
        inference_timestamp_ms
        if inference_timestamp_ms is not None
        else time.time() * 1000
    )

    # Model masih dilatih dari data simulasi.
    result["model_stage"] = "PROTOTYPE_SIMULATION"
    result["model_version"] = "prototype-v1"
    result["data_source"] = DATA_SOURCE_LABELS.get(
        data_root,
        data_root.upper(),
    )
    result["time_mode"] = time_mode

    return result


def process_pending_record(
    input_df,
    target_timestamp,
    time_mode,
    model_bundle,
    write_latest=False,
):
    """
    Analisis tepat satu record history.

    Data sebelum target tetap dipertahankan agar fitur
    temporal/rate-of-change mempunyai konteks.
    """

    result = build_analysis_result(
        input_df,
        target_timestamp,
        time_mode,
        model_bundle,
        DATA_ROOT,
    )

    if result is None:
        return None


    if DRY_RUN:
        print("[DRY-RUN] Prediksi tidak ditulis ke Firebase")
    else:
        # Arsip analisis pada timestamp yang tepat.
        db.reference(
            f"{DATA_ROOT}/history/"
            f"{target_timestamp}/analysis"
        ).set(result)


        # /analysis/latest hanya boleh diperbarui jika
        # record yang sedang diproses memang data terbaru.
        if write_latest:

            db.reference(
                f"{DATA_ROOT}/analysis/latest"
            ).set(result)


    rf = result[
        "random_forest"
    ]


    print()
    print(
        f"PROCESSING  : "
        f"{target_timestamp}"
    )
    print(
        f"Status      : "
        f"{result['status']}"
    )
    print(
        f"Lokasi      : "
        f"{result['location']}"
    )
    print(
        f"RF          : "
        f"{rf['prediction']}"
    )
    print(
        f"Confidence  : "
        f"{rf['confidence'] * 100:.1f}%"
    )
    print(
        f"IF anomaly  : "
        f"{result['isolation_forest']['is_anomaly']}"
    )
    print(
        f"Dominan     : "
        f"{result['dominant_zscore']['parameter']} "
        f"{result['dominant_zscore']['node']}"
    )
    print(
        f"Z-score     : "
        f"{result['dominant_zscore']['zscore']:.2f}"
    )
    print(
        "✓ Dry-run selesai (tidak disimpan)"
        if DRY_RUN else "✓ Analysis saved"
    )


    return result



def recover_full_backlog(
    model_bundle,
):
    """
    Startup recovery.

    Membaca seluruh history pada DATA_ROOT dan
    menganalisis semua record valid yang belum
    mempunyai /analysis.

    Setelah recovery selesai, realtime loop kembali
    memakai HISTORY_LIMIT agar tetap ringan.
    """

    print()
    print(
        "Memeriksa backlog history..."
    )

    (
        input_df,
        pending_timestamps,
        time_mode
    ) = load_recent_history(
        limit=None
    )


    if input_df is None:

        print(
            "Recovery: belum cukup "
            "history valid."
        )

        return


    if not pending_timestamps:

        print(
            "Recovery: tidak ada "
            "record tertinggal."
        )

        return


    pending_timestamps = sorted(
        int(timestamp)
        for timestamp
        in pending_timestamps
    )


    newest_timestamp = int(
        input_df[
            "source_timestamp_ms"
        ].max()
    )


    print(
        f"Recovery menemukan "
        f"{len(pending_timestamps)} "
        f"record belum dianalisis."
    )


    for index, target_timestamp in enumerate(
        pending_timestamps,
        start=1,
    ):

        print(
            f"[{index}/"
            f"{len(pending_timestamps)}]"
        )

        process_pending_record(
            input_df=input_df,

            target_timestamp=
                target_timestamp,

            time_mode=
                time_mode,

            model_bundle=
                model_bundle,

            write_latest=(
                target_timestamp
                == newest_timestamp
            ),
        )


    print()
    print(
        "✓ Full backlog recovery selesai."
    )


def main():

    global DATA_ROOT, DATA_MODE, DRY_RUN

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

    parser.add_argument(
        "--root",
        choices=("simulation", "real_test", "hardware_test"),
        default=None,
        help="Pilih data root tanpa mengubah tasnim.config.json",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Jalankan analisis tanpa Firebase write",
    )

    args = parser.parse_args()

    # TASNIM_AI_CLI_V1
    if args.root is not None:
        DATA_ROOT = args.root
        DATA_MODE = args.root.upper()

    DRY_RUN = args.dry_run

    print(
        f"[MODE] root={DATA_ROOT} | "
        f"dry_run={DRY_RUN}"
    )


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

    # Periksa seluruh backlog sekali saat AI startup.
    # Setelah itu loop realtime kembali memakai
    # HISTORY_LIMIT agar tetap ringan.
    recover_full_backlog(
        model_bundle
    )

    wait_state = None

    try:

        while True:

            (
                input_df,
                pending_timestamps,
                time_mode
            ) = load_recent_history()


            # Pesan tunggu dicetak sekali per perubahan status,
            # bukan setiap 5 detik.
            if input_df is None:

                if wait_state != "NO_HISTORY":
                    print(
                        "Menunggu minimal 2 slot "
                        "history lengkap N0/N1/N2..."
                    )
                wait_state = "NO_HISTORY"


            elif not pending_timestamps:

                if wait_state != "IDLE":
                    print(
                        "Tidak ada record yang "
                        "menunggu analisis."
                    )
                wait_state = "IDLE"


            else:

                pending_timestamps = sorted(
                    int(timestamp)
                    for timestamp
                    in pending_timestamps
                )


                newest_timestamp = int(
                    input_df[
                        "source_timestamp_ms"
                    ].max()
                )


                wait_state = None

                print()
                print(
                    f"{len(pending_timestamps)} "
                    f"record menunggu analisis."
                )


                for target_timestamp in (
                    pending_timestamps
                ):

                    process_pending_record(
                        input_df=
                            input_df,

                        target_timestamp=
                            target_timestamp,

                        time_mode=
                            time_mode,

                        model_bundle=
                            model_bundle,

                        write_latest=(
                            target_timestamp
                            == newest_timestamp
                        ),
                    )


                print()
                print(
                    "Backlog selesai."
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
