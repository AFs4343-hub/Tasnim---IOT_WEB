from __future__ import annotations

import numpy as np
import pandas as pd


# ============================================================
# KONFIGURASI FITUR
# ============================================================

NODES = ["N0", "N1", "N2"]

PARAMETERS = [
    "ph",
    "tds",
    "turbidity",
]


# 9 fitur sensor mentah
RAW_FEATURES = [
    f"{parameter}_{node}"
    for parameter in PARAMETERS
    for node in NODES
]


# 6 fitur spasial
DELTA_FEATURES = [
    f"delta_{parameter}_N01"
    for parameter in PARAMETERS
] + [
    f"delta_{parameter}_N02"
    for parameter in PARAMETERS
]


# 9 fitur temporal
RATE_FEATURES = [
    f"rate_{parameter}_{node}"
    for parameter in PARAMETERS
    for node in NODES
]


# 9 fitur statistik
ZSCORE_FEATURES = [
    f"z_{feature}"
    for feature in RAW_FEATURES
]


# Total 33 fitur yang nantinya masuk model
MODEL_FEATURES = (
    RAW_FEATURES
    + DELTA_FEATURES
    + RATE_FEATURES
    + ZSCORE_FEATURES
)


# ============================================================
# FITUR SPASIAL + TEMPORAL
# ============================================================

def add_base_features(
    df: pd.DataFrame,
) -> pd.DataFrame:

    out = df.copy()

    # Timestamp harus bertipe datetime
    out["timestamp"] = pd.to_datetime(
        out["timestamp"]
    )

    # Pastikan urutan waktu benar di setiap sesi
    out = out.sort_values(
        ["session_id", "timestamp"]
    ).reset_index(drop=True)

    # ========================================================
    # 1. DELTA SPASIAL
    #
    # ΔX N0->N1 = X_N1 - X_N0
    # ΔX N0->N2 = X_N2 - X_N0
    # ========================================================

    for parameter in PARAMETERS:

        out[f"delta_{parameter}_N01"] = (
            out[f"{parameter}_N1"]
            - out[f"{parameter}_N0"]
        )

        out[f"delta_{parameter}_N02"] = (
            out[f"{parameter}_N2"]
            - out[f"{parameter}_N0"]
        )

    # ========================================================
    # 2. RATE OF CHANGE
    #
    # rate = perubahan nilai / perubahan waktu dalam menit
    #
    # Perhitungan dilakukan PER SESSION supaya akhir S001
    # tidak dibandingkan dengan awal S002.
    # ========================================================

    for parameter in PARAMETERS:

        for node in NODES:

            value_column = (
                f"{parameter}_{node}"
            )

            rate_column = (
                f"rate_{parameter}_{node}"
            )

            delta_value = (
                out.groupby("session_id")[
                    value_column
                ]
                .diff()
            )

            delta_time_minutes = (
                out.groupby("session_id")[
                    "timestamp"
                ]
                .diff()
                .dt.total_seconds()
                .div(60.0)
            )

            out[rate_column] = (
                delta_value
                / delta_time_minutes.replace(
                    0,
                    np.nan
                )
            )

    # Baris pertama setiap sesi tidak memiliki data sebelumnya.
    # Untuk prototype, rate pertama diisi 0.
    out[RATE_FEATURES] = (
        out[RATE_FEATURES]
        .replace(
            [np.inf, -np.inf],
            np.nan
        )
        .fillna(0.0)
    )

    return out


# ============================================================
# FIT STATISTIK NORMAL UNTUK Z-SCORE
# ============================================================

def fit_normal_zscore_stats(
    train_df: pd.DataFrame,
    label_column: str = "label",
) -> dict:

    # HANYA kondisi NORMAL di TRAIN SET.
    normal_data = train_df[
        train_df[label_column]
        == "NORMAL"
    ]

    if normal_data.empty:
        raise ValueError(
            "Training set tidak memiliki data NORMAL."
        )

    stats = {}

    for feature in RAW_FEATURES:

        mean = float(
            normal_data[feature].mean()
        )

        std = float(
            normal_data[feature].std(
                ddof=1
            )
        )

        # Proteksi kalau standar deviasi 0 / invalid
        if (
            not np.isfinite(std)
            or std == 0
        ):
            std = 1.0

        stats[feature] = {
            "mean": mean,
            "std": std,
        }

    return stats


# ============================================================
# APLIKASIKAN Z-SCORE
# ============================================================

def apply_zscores(
    df: pd.DataFrame,
    stats: dict,
) -> pd.DataFrame:

    out = df.copy()

    for feature in RAW_FEATURES:

        mean = stats[feature]["mean"]
        std = stats[feature]["std"]

        out[f"z_{feature}"] = (
            (out[feature] - mean)
            / std
        )

    return out


# ============================================================
# MATRIKS FINAL UNTUK MODEL
# ============================================================

def prepare_model_matrix(
    df: pd.DataFrame,
) -> pd.DataFrame:

    missing = [
        feature
        for feature in MODEL_FEATURES
        if feature not in df.columns
    ]

    if missing:
        raise ValueError(
            "Fitur model belum lengkap: "
            + ", ".join(missing)
        )

    X = (
        df[MODEL_FEATURES]
        .replace(
            [np.inf, -np.inf],
            np.nan
        )
        .fillna(0.0)
        .astype(float)
    )

    return X
