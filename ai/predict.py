import argparse
import json
from pathlib import Path

import joblib
import pandas as pd

from ai.features import (
    RAW_FEATURES,
    add_base_features,
    apply_zscores,
    prepare_model_matrix,
)


MODEL_PATH = Path(
    "ai/models/tasnim_ai_bundle.joblib"
)

DEFAULT_INPUT = Path(
    "ai/data/simulated_raw.csv"
)

DEFAULT_OUTPUT = Path(
    "ai/outputs/latest_prediction.json"
)


# ============================================================
# INTERPRETASI LOKASI
# ============================================================

def get_location(prediction: str):

    if prediction == "NORMAL":
        return None

    if prediction.startswith(
        "ANOMALI_"
    ):
        return prediction.replace(
            "ANOMALI_",
            ""
        )

    return None


# ============================================================
# CARI Z-SCORE PALING DOMINAN
# ============================================================

def get_dominant_zscore(row):

    z_columns = [
        f"z_{feature}"
        for feature in RAW_FEATURES
    ]

    dominant_column = max(
        z_columns,
        key=lambda column:
            abs(float(row[column]))
    )

    value = float(
        row[dominant_column]
    )

    # z_tds_N2 -> tds_N2
    sensor_feature = (
        dominant_column
        .replace("z_", "", 1)
    )

    parameter, node = (
        sensor_feature
        .rsplit("_", 1)
    )

    return {
        "feature":
            sensor_feature,

        "parameter":
            parameter,

        "node":
            node,

        "zscore":
            value,

        "absolute_zscore":
            abs(value),
    }


# ============================================================
# PREDIKSI
# ============================================================

def predict_latest(
    input_df,
    model_bundle,
):

    # --------------------------------------------------------
    # Feature engineering
    # --------------------------------------------------------

    feature_df = add_base_features(
        input_df
    )

    feature_df = apply_zscores(
        feature_df,
        model_bundle[
            "zscore_stats"
        ]
    )

    X = prepare_model_matrix(
        feature_df
    )

    # --------------------------------------------------------
    # Load model
    # --------------------------------------------------------

    random_forest = (
        model_bundle[
            "random_forest"
        ]
    )

    isolation_forest = (
        model_bundle[
            "isolation_forest"
        ]
    )

    # --------------------------------------------------------
    # RANDOM FOREST
    # --------------------------------------------------------

    rf_prediction_all = (
        random_forest.predict(
            X
        )
    )

    rf_probability_all = (
        random_forest.predict_proba(
            X
        )
    )

    latest_prediction = str(
        rf_prediction_all[-1]
    )

    latest_probability = (
        rf_probability_all[-1]
    )

    probabilities = {
        str(class_name):
            float(probability)

        for class_name, probability
        in zip(
            random_forest.classes_,
            latest_probability,
        )
    }

    confidence = float(
        max(
            latest_probability
        )
    )

    # --------------------------------------------------------
    # ISOLATION FOREST
    # --------------------------------------------------------

    iso_prediction_all = (
        isolation_forest.predict(
            X
        )
    )

    iso_score_all = (
        isolation_forest.decision_function(
            X
        )
    )

    latest_iso_prediction = int(
        iso_prediction_all[-1]
    )

    latest_iso_score = float(
        iso_score_all[-1]
    )

    # --------------------------------------------------------
    # DATA TERAKHIR
    # --------------------------------------------------------

    latest_row = (
        feature_df.iloc[-1]
    )

    zscore_result = (
        get_dominant_zscore(
            latest_row
        )
    )

    # --------------------------------------------------------
    # OUTPUT
    # --------------------------------------------------------

    result = {

        "timestamp":
            pd.to_datetime(
                latest_row[
                    "timestamp"
                ]
            ).isoformat(),

        "session_id":
            str(
                latest_row[
                    "session_id"
                ]
            ),

        "status":
            (
                "NORMAL"
                if latest_prediction
                == "NORMAL"
                else "ANOMALI"
            ),

        "location":
            get_location(
                latest_prediction
            ),

        "random_forest": {

            "prediction":
                latest_prediction,

            "confidence":
                confidence,

            "probabilities":
                probabilities,
        },

        "isolation_forest": {

            "is_anomaly":
                bool(
                    latest_iso_prediction
                    == -1
                ),

            "decision_score":
                latest_iso_score,
        },

        "dominant_zscore":
            zscore_result,
    }

    # --------------------------------------------------------
    # Ground truth hanya untuk DEMO dataset simulasi
    # --------------------------------------------------------

    if "label" in feature_df.columns:

        result[
            "simulation_ground_truth"
        ] = str(
            latest_row[
                "label"
            ]
        )

        result[
            "prediction_correct"
        ] = bool(
            latest_prediction
            == str(
                latest_row[
                    "label"
                ]
            )
        )

    return result


# ============================================================
# MAIN
# ============================================================

def main():

    parser = argparse.ArgumentParser(
        description=(
            "Prediksi AI TASNIM"
        )
    )

    parser.add_argument(
        "--input",
        default=str(
            DEFAULT_INPUT
        ),
    )

    parser.add_argument(
        "--output",
        default=str(
            DEFAULT_OUTPUT
        ),
    )

    args = parser.parse_args()

    input_path = Path(
        args.input
    )

    output_path = Path(
        args.output
    )

    # --------------------------------------------------------
    # Validasi
    # --------------------------------------------------------

    if not MODEL_PATH.exists():

        raise FileNotFoundError(
            "Model belum ditemukan. "
            "Jalankan:\n"
            "python3 ai/train_models.py"
        )

    if not input_path.exists():

        raise FileNotFoundError(
            f"Input tidak ditemukan: "
            f"{input_path}"
        )

    # --------------------------------------------------------
    # Load
    # --------------------------------------------------------

    model_bundle = joblib.load(
        MODEL_PATH
    )

    df = pd.read_csv(
        input_path
    )

    if df.empty:
        raise ValueError(
            "Dataset input kosong."
        )

    # --------------------------------------------------------
    # Untuk demo kita gunakan sesi terakhir.
    #
    # Penting:
    # rate-of-change membutuhkan data sebelumnya,
    # jadi jangan hanya memberi satu baris.
    # --------------------------------------------------------

    latest_session = (
        df["session_id"]
        .iloc[-1]
    )

    session_df = (
        df[
            df["session_id"]
            == latest_session
        ]
        .copy()
    )

    result = predict_latest(
        session_df,
        model_bundle,
    )

    # --------------------------------------------------------
    # Simpan JSON
    # --------------------------------------------------------

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    output_path.write_text(
        json.dumps(
            result,
            indent=2
        ),
        encoding="utf-8"
    )

    print()
    print(
        "======================================"
    )

    print(
        " PREDIKSI AI TASNIM"
    )

    print(
        "======================================"
    )

    print(
        json.dumps(
            result,
            indent=2
        )
    )

    print()
    print(
        "Hasil tersimpan:"
    )

    print(
        output_path
    )


if __name__ == "__main__":
    main()
