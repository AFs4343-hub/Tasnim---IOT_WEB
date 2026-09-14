import json
from pathlib import Path

import joblib
import pandas as pd

from sklearn.ensemble import (
    RandomForestClassifier,
    IsolationForest,
)

from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    classification_report,
    confusion_matrix,
)

from sklearn.model_selection import (
    GroupShuffleSplit,
)

from ai.features import (
    MODEL_FEATURES,
    add_base_features,
    fit_normal_zscore_stats,
    apply_zscores,
    prepare_model_matrix,
)


# ============================================================
# PATH
# ============================================================

DATA_PATH = Path(
    "ai/data/simulated_raw.csv"
)

MODEL_PATH = Path(
    "ai/models/tasnim_ai_bundle.joblib"
)

METRICS_PATH = Path(
    "ai/outputs/metrics.json"
)

CONFUSION_PATH = Path(
    "ai/outputs/confusion_matrix.csv"
)

IMPORTANCE_PATH = Path(
    "ai/outputs/feature_importance.csv"
)


# ============================================================
# EVALUASI RANDOM FOREST
# ============================================================

def evaluate_random_forest(
    y_true,
    y_pred,
):
    return {
        "accuracy": float(
            accuracy_score(
                y_true,
                y_pred
            )
        ),

        "precision_macro": float(
            precision_score(
                y_true,
                y_pred,
                average="macro",
                zero_division=0,
            )
        ),

        "recall_macro": float(
            recall_score(
                y_true,
                y_pred,
                average="macro",
                zero_division=0,
            )
        ),

        "f1_macro": float(
            f1_score(
                y_true,
                y_pred,
                average="macro",
                zero_division=0,
            )
        ),
    }


# ============================================================
# MAIN
# ============================================================

def main():

    print()
    print(
        "======================================"
    )

    print(
        " TRAINING AI TASNIM"
    )

    print(
        "======================================"
    )

    # --------------------------------------------------------
    # 1. LOAD DATA
    # --------------------------------------------------------

    if not DATA_PATH.exists():
        raise FileNotFoundError(
            f"{DATA_PATH} tidak ditemukan.\n"
            "Jalankan generate_data.py dulu."
        )

    raw_df = pd.read_csv(
        DATA_PATH
    )

    print(
        f"Raw dataset : {raw_df.shape}"
    )

    # --------------------------------------------------------
    # 2. FEATURE ENGINEERING DASAR
    # --------------------------------------------------------

    df = add_base_features(
        raw_df
    )

    # --------------------------------------------------------
    # 3. SPLIT BERDASARKAN SESSION
    #
    # Tidak random row agar data berdekatan tidak bocor
    # antara training dan test.
    # --------------------------------------------------------

    splitter = GroupShuffleSplit(
        n_splits=1,
        test_size=0.25,
        random_state=42,
    )

    train_index, test_index = next(
        splitter.split(
            df,
            groups=df["session_id"],
        )
    )

    train_df = (
        df
        .iloc[train_index]
        .copy()
    )

    test_df = (
        df
        .iloc[test_index]
        .copy()
    )

    train_sessions = sorted(
        train_df[
            "session_id"
        ].unique()
    )

    test_sessions = sorted(
        test_df[
            "session_id"
        ].unique()
    )

    print()
    print(
        f"Train rows : {len(train_df)}"
    )

    print(
        f"Test rows  : {len(test_df)}"
    )

    print(
        f"Train sessions : "
        f"{len(train_sessions)}"
    )

    print(
        f"Test sessions  : "
        f"{len(test_sessions)}"
    )

    print()
    print(
        "Train label distribution:"
    )

    print(
        train_df["label"]
        .value_counts()
        .to_string()
    )

    print()
    print(
        "Test label distribution:"
    )

    print(
        test_df["label"]
        .value_counts()
        .to_string()
    )

    # --------------------------------------------------------
    # 4. FIT Z-SCORE HANYA PADA NORMAL TRAINING
    # --------------------------------------------------------

    zscore_stats = (
        fit_normal_zscore_stats(
            train_df
        )
    )

    train_df = apply_zscores(
        train_df,
        zscore_stats
    )

    test_df = apply_zscores(
        test_df,
        zscore_stats
    )

    # --------------------------------------------------------
    # 5. BENTUK MATRIKS MODEL
    # --------------------------------------------------------

    X_train = (
        prepare_model_matrix(
            train_df
        )
    )

    X_test = (
        prepare_model_matrix(
            test_df
        )
    )

    y_train = (
        train_df["label"]
        .astype(str)
    )

    y_test = (
        test_df["label"]
        .astype(str)
    )

    print()
    print(
        f"Jumlah fitur model : "
        f"{X_train.shape[1]}"
    )

    # ========================================================
    # RANDOM FOREST
    # ========================================================

    print()
    print(
        "======================================"
    )

    print(
        " RANDOM FOREST"
    )

    print(
        "======================================"
    )

    random_forest = (
        RandomForestClassifier(
            n_estimators=350,

            class_weight="balanced",

            min_samples_leaf=2,

            random_state=42,

            n_jobs=-1,
        )
    )

    random_forest.fit(
        X_train,
        y_train
    )

    rf_prediction = (
        random_forest.predict(
            X_test
        )
    )

    rf_metrics = (
        evaluate_random_forest(
            y_test,
            rf_prediction
        )
    )

    print()
    print(
        classification_report(
            y_test,
            rf_prediction,
            zero_division=0,
        )
    )

    print(
        "Accuracy       :",
        round(
            rf_metrics["accuracy"],
            4
        )
    )

    print(
        "Precision Macro:",
        round(
            rf_metrics[
                "precision_macro"
            ],
            4
        )
    )

    print(
        "Recall Macro   :",
        round(
            rf_metrics[
                "recall_macro"
            ],
            4
        )
    )

    print(
        "F1 Macro       :",
        round(
            rf_metrics[
                "f1_macro"
            ],
            4
        )
    )

    # --------------------------------------------------------
    # CONFUSION MATRIX
    # --------------------------------------------------------

    labels = sorted(
        set(y_test)
        | set(rf_prediction)
    )

    matrix = confusion_matrix(
        y_test,
        rf_prediction,
        labels=labels,
    )

    confusion_df = pd.DataFrame(
        matrix,

        index=[
            f"true_{label}"
            for label in labels
        ],

        columns=[
            f"pred_{label}"
            for label in labels
        ],
    )

    CONFUSION_PATH.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    confusion_df.to_csv(
        CONFUSION_PATH
    )

    print()
    print(
        "Confusion Matrix:"
    )

    print(
        confusion_df.to_string()
    )

    # --------------------------------------------------------
    # FEATURE IMPORTANCE
    # --------------------------------------------------------

    importance_df = pd.DataFrame(
        {
            "feature":
                MODEL_FEATURES,

            "importance":
                random_forest
                .feature_importances_,
        }
    )

    importance_df = (
        importance_df
        .sort_values(
            "importance",
            ascending=False
        )
    )

    importance_df.to_csv(
        IMPORTANCE_PATH,
        index=False
    )

    print()
    print(
        "Top 10 Feature Importance:"
    )

    print(
        importance_df
        .head(10)
        .to_string(
            index=False
        )
    )

    # ========================================================
    # ISOLATION FOREST
    # ========================================================

    print()
    print(
        "======================================"
    )

    print(
        " ISOLATION FOREST"
    )

    print(
        "======================================"
    )

    # Isolation Forest dilatih HANYA dengan data NORMAL
    normal_train_df = (
        train_df[
            train_df["label"]
            == "NORMAL"
        ]
        .copy()
    )

    X_normal_train = (
        prepare_model_matrix(
            normal_train_df
        )
    )

    isolation_forest = (
        IsolationForest(
            n_estimators=300,

            contamination="auto",

            random_state=42,

            n_jobs=-1,
        )
    )

    isolation_forest.fit(
        X_normal_train
    )

    # sklearn:
    # +1 = inlier / normal
    # -1 = outlier / anomali

    iso_raw_prediction = (
        isolation_forest.predict(
            X_test
        )
    )

    iso_anomaly_prediction = (
        iso_raw_prediction == -1
    )

    actual_anomaly = (
        y_test != "NORMAL"
    )

    iso_metrics = {

        "accuracy": float(
            accuracy_score(
                actual_anomaly,
                iso_anomaly_prediction,
            )
        ),

        "precision": float(
            precision_score(
                actual_anomaly,
                iso_anomaly_prediction,
                zero_division=0,
            )
        ),

        "recall": float(
            recall_score(
                actual_anomaly,
                iso_anomaly_prediction,
                zero_division=0,
            )
        ),

        "f1": float(
            f1_score(
                actual_anomaly,
                iso_anomaly_prediction,
                zero_division=0,
            )
        ),
    }

    print(
        "Accuracy :",
        round(
            iso_metrics["accuracy"],
            4
        )
    )

    print(
        "Precision:",
        round(
            iso_metrics["precision"],
            4
        )
    )

    print(
        "Recall   :",
        round(
            iso_metrics["recall"],
            4
        )
    )

    print(
        "F1       :",
        round(
            iso_metrics["f1"],
            4
        )
    )

    # ========================================================
    # SIMPAN MODEL
    # ========================================================

    MODEL_PATH.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    model_bundle = {

        "random_forest":
            random_forest,

        "isolation_forest":
            isolation_forest,

        "zscore_stats":
            zscore_stats,

        "feature_columns":
            MODEL_FEATURES,

        "rf_classes":
            list(
                random_forest.classes_
            ),

        "metadata": {

            "prototype":
                True,

            "dataset":
                str(DATA_PATH),

            "split_strategy":
                "GroupShuffleSplit by session_id",

            "train_sessions":
                train_sessions,

            "test_sessions":
                test_sessions,
        }
    }

    joblib.dump(
        model_bundle,
        MODEL_PATH
    )

    # ========================================================
    # SIMPAN METRIK
    # ========================================================

    metrics = {

        "random_forest":
            rf_metrics,

        "isolation_forest":
            iso_metrics,

        "train_rows":
            int(len(train_df)),

        "test_rows":
            int(len(test_df)),

        "train_sessions":
            train_sessions,

        "test_sessions":
            test_sessions,

        "number_of_features":
            len(MODEL_FEATURES),

        "warning":
            (
                "Semua metrik berasal dari "
                "dataset simulasi dan bukan "
                "hasil final penelitian."
            )
    }

    METRICS_PATH.write_text(
        json.dumps(
            metrics,
            indent=2
        ),
        encoding="utf-8"
    )

    print()
    print(
        "======================================"
    )

    print(
        " TRAINING SELESAI"
    )

    print(
        "======================================"
    )

    print(
        f"Model:"
        f"\n{MODEL_PATH}"
    )

    print(
        f"\nMetrics:"
        f"\n{METRICS_PATH}"
    )

    print(
        f"\nConfusion Matrix:"
        f"\n{CONFUSION_PATH}"
    )

    print(
        f"\nFeature Importance:"
        f"\n{IMPORTANCE_PATH}"
    )

    print()
    print(
        "CATATAN:"
    )

    print(
        "Hasil ini hanya evaluasi "
        "dataset simulasi."
    )

    print(
        "Jangan digunakan sebagai "
        "klaim akurasi final TASNIM."
    )


if __name__ == "__main__":
    main()
