from pathlib import Path

import numpy as np
import pandas as pd


# ============================================================
# KONFIGURASI
# ============================================================

SEED = 42

JUMLAH_SESI = 32
SAMPEL_PER_SESI = 72
INTERVAL_MENIT = 5

NODES = ["N0", "N1", "N2"]
PARAMETERS = ["ph", "tds", "turbidity"]

OUTPUT_PATH = Path("ai/data/simulated_raw.csv")


# ============================================================
# GENERATOR DATA
# ============================================================

def generate_dataset():
    rng = np.random.default_rng(SEED)

    rows = []

    waktu_awal = pd.Timestamp("2026-09-01 08:00:00")

    for session_index in range(JUMLAH_SESI):

        session_id = f"S{session_index + 1:03d}"

        session_start = (
            waktu_awal
            + pd.Timedelta(days=session_index)
        )

        # ----------------------------------------------------
        # Baseline simulasi setiap sesi
        #
        # Angka ini hanya untuk pengujian software/pipeline.
        # BUKAN batas aman atau standar biologis kualitas air.
        # ----------------------------------------------------

        base_ph = rng.normal(7.20, 0.07)
        base_tds = rng.normal(210, 7)

        base_turbidity = max(
            2.0,
            rng.normal(8.0, 1.2)
        )

        # ----------------------------------------------------
        # Sebagian sesi diberi event anomali sintetis
        # ----------------------------------------------------

        has_anomaly = rng.random() < 0.80

        anomaly_node = None
        anomaly_parameter = None
        anomaly_start = -1
        anomaly_end = -1
        ph_direction = 1.0

        if has_anomaly:

            anomaly_node = rng.choice(NODES)

            anomaly_parameter = rng.choice(
                PARAMETERS
            )

            anomaly_length = int(
                rng.integers(6, 15)
            )

            anomaly_start = int(
                rng.integers(
                    10,
                    SAMPEL_PER_SESI
                    - anomaly_length
                    - 5
                )
            )

            anomaly_end = (
                anomaly_start
                + anomaly_length
            )

            if anomaly_parameter == "ph":
                ph_direction = float(
                    rng.choice([-1, 1])
                )

        # ----------------------------------------------------
        # Perbedaan kecil alami antar-node
        # ----------------------------------------------------

        node_offset = {

            "N0": {
                "ph": 0.0,
                "tds": 0.0,
                "turbidity": 0.0
            },

            "N1": {
                "ph": rng.normal(-0.02, 0.015),
                "tds": rng.normal(2.0, 1.5),
                "turbidity": rng.normal(0.5, 0.3)
            },

            "N2": {
                "ph": rng.normal(-0.01, 0.015),
                "tds": rng.normal(1.0, 1.5),
                "turbidity": rng.normal(0.3, 0.3)
            }
        }

        # ====================================================
        # DERET WAKTU DALAM SATU SESI
        # ====================================================

        for i in range(SAMPEL_PER_SESI):

            timestamp = (
                session_start
                + pd.Timedelta(
                    minutes=i * INTERVAL_MENIT
                )
            )

            phase = (
                2
                * np.pi
                * i
                / SAMPEL_PER_SESI
            )

            row = {
                "timestamp": timestamp,
                "session_id": session_id,
                "label": "NORMAL",
                "anomaly_parameter": "NONE"
            }

            # =================================================
            # NILAI SENSOR SETIAP NODE
            # =================================================

            for node in NODES:

                ph = (
                    base_ph
                    + node_offset[node]["ph"]
                    + 0.05 * np.sin(phase)
                    + rng.normal(0, 0.025)
                )

                tds = (
                    base_tds
                    + node_offset[node]["tds"]
                    + 4.0 * np.sin(phase / 2)
                    + rng.normal(0, 2.5)
                )

                turbidity = (
                    base_turbidity
                    + node_offset[node]["turbidity"]
                    + 0.8 * np.sin(phase)
                    + rng.normal(0, 0.55)
                )

                # ---------------------------------------------
                # Apakah event anomali sedang aktif?
                # ---------------------------------------------

                anomaly_active = (
                    has_anomaly
                    and node == anomaly_node
                    and anomaly_start <= i < anomaly_end
                )

                if anomaly_active:

                    progress = (
                        (i - anomaly_start + 1)
                        / (anomaly_end - anomaly_start)
                    )

                    if anomaly_parameter == "ph":

                        ph += (
                            ph_direction
                            * (
                                0.45
                                + 0.55 * progress
                            )
                        )

                    elif anomaly_parameter == "tds":

                        tds += (
                            35
                            + 75 * progress
                        )

                    elif anomaly_parameter == "turbidity":

                        turbidity += (
                            8
                            + 25 * progress
                        )

                    row["label"] = (
                        f"ANOMALI_{node}"
                    )

                    row[
                        "anomaly_parameter"
                    ] = anomaly_parameter

                # ---------------------------------------------
                # Simpan nilai sensor
                # ---------------------------------------------

                row[f"ph_{node}"] = round(
                    float(ph),
                    3
                )

                row[f"tds_{node}"] = round(
                    float(max(tds, 0)),
                    3
                )

                row[
                    f"turbidity_{node}"
                ] = round(
                    float(
                        max(turbidity, 0)
                    ),
                    3
                )

            rows.append(row)

    return pd.DataFrame(rows)


# ============================================================
# MAIN
# ============================================================

def main():

    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    df = generate_dataset()

    df.to_csv(
        OUTPUT_PATH,
        index=False
    )

    print()
    print("===================================")
    print(" DATASET SIMULASI AI TASNIM")
    print("===================================")

    print(
        f"Jumlah baris       : {len(df)}"
    )

    print(
        f"Jumlah sesi        : "
        f"{df['session_id'].nunique()}"
    )

    print(
        f"Interval simulasi  : "
        f"{INTERVAL_MENIT} menit"
    )

    print()
    print("Distribusi label:")
    print(
        df["label"]
        .value_counts()
        .to_string()
    )

    print()
    print("Distribusi parameter anomali:")
    print(
        df["anomaly_parameter"]
        .value_counts()
        .to_string()
    )

    print()
    print(
        f"Dataset tersimpan:"
        f"\n{OUTPUT_PATH}"
    )


if __name__ == "__main__":
    main()
