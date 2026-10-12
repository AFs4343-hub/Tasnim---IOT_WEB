"""Hardware V2 AI preview orchestration (pure offline dry run).

A caller supplies an existing model and predictor, which keeps this module
separate from Firebase Admin initialization and any database write path.
The model is still a simulation-trained prototype, not field ground truth.
"""

from ai.hardware_test_history_v2 import (
    model_frame_for_slot, prepare_backlog,
)


def annotate_preview(prediction, *, slot, time_mode):
    """Add traceability and transparent model-disagreement diagnostics."""
    if not isinstance(prediction, dict):
        raise ValueError("prediction:expected_dict")
    rf = prediction.get("random_forest")
    iso = prediction.get("isolation_forest")
    if not isinstance(rf, dict) or not isinstance(iso, dict):
        raise ValueError("prediction:missing_model_details")
    rf_name = rf.get("prediction")
    iso_anomaly = iso.get("is_anomaly")
    if not isinstance(rf_name, str) or type(iso_anomaly) is not bool:
        raise ValueError("prediction:invalid_model_details")

    rf_anomaly = rf_name != "NORMAL"
    disagreement = rf_anomaly != iso_anomaly
    result = dict(prediction)
    result.update({
        "source_timestamp_ms": slot,
        "data_source": "HARDWARE_TEST",
        "model_stage": "PROTOTYPE_SIMULATION",
        "time_mode": time_mode,
        "model_disagreement": disagreement,
        "interpretation": (
            "MODEL_REVIEW_REQUIRED" if disagreement
            else "PROTOTYPE_NOT_FIELD_VALIDATED"
        ),
    })
    return result


def preview_pending(history, *, session_id, model_bundle, predict_fn):
    """Run pending slots oldest-first, without Firebase/network access.

    Returns a plan and candidate predictions. This does not send acknowledgments,
    persist analysis, or change data permissions.
    """
    if not callable(predict_fn):
        raise ValueError("predict_fn:must_be_callable")
    plan = prepare_backlog(history, session_id=session_id)
    predictions = {}
    for slot in plan["pending_timestamps"]:
        frame = model_frame_for_slot(plan, slot)
        candidate = predict_fn(frame, model_bundle)
        predictions[str(slot)] = annotate_preview(
            candidate, slot=slot, time_mode=plan["time_mode"]
        )
    return {"plan": plan, "predictions": predictions}
