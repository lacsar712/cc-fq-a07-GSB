"""Server-side job diffing.

The diff is computed HERE, never by subtracting two job-detail payloads in the
browser. Frontends only render the returned structure (values, deltas, missing
flags and stage status pairs).
"""

from __future__ import annotations

from typing import Any

from app.models import Job, JobStage
from app.pipeline.runner import STAGE_NAMES

# The three headline QC metrics surfaced on the detail page.
METRIC_KEYS: tuple[tuple[str, str], ...] = (
    ("reads", "reads"),
    ("mean_quality", "mean_quality"),
    ("n_rate", "n_rate"),
)

# Floating-point metrics need bounded rounding for the displayed delta.
FLOAT_KEYS = {"mean_quality", "n_rate"}
DELTA_ROUND = 6


def _metric_value(metrics: dict[str, Any] | None, key: str) -> Any:
    """Read a headline metric, falling back to the flattened summary block."""
    if not metrics:
        return None
    value = metrics.get(key)
    if value is None:
        value = (metrics.get("summary") or {}).get(key)
    return value


def _is_present(value: Any) -> bool:
    return value is not None


def _delta(value_a: Any, value_b: Any, key: str) -> Any:
    delta = value_a - value_b
    if key in FLOAT_KEYS:
        return round(float(delta), DELTA_ROUND)
    return int(delta)


def build_metric_diffs(job_a: Job, job_b: Job) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for key, label in METRIC_KEYS:
        value_a = _metric_value(job_a.metrics, key)
        value_b = _metric_value(job_b.metrics, key)
        present_a = _is_present(value_a)
        present_b = _is_present(value_b)
        both_missing = not present_a and not present_b
        both_present = present_a and present_b
        equal = (
            both_missing or (both_present and value_a == value_b)
        )
        result.append(
            {
                "key": key,
                "label": label,
                "value_a": value_a,
                "value_b": value_b,
                "present_a": present_a,
                "present_b": present_b,
                "both_missing": both_missing,
                "delta": _delta(value_a, value_b, key) if both_present else None,
                "equal": equal,
            }
        )
    return result


def build_stage_diffs(
    stages_a: list[JobStage], stages_b: list[JobStage]
) -> list[dict[str, Any]]:
    by_name_a = {s.actor_name: s for s in stages_a}
    by_name_b = {s.actor_name: s for s in stages_b}
    result: list[dict[str, Any]] = []
    for order, name in enumerate(STAGE_NAMES):
        stage_a = by_name_a.get(name)
        stage_b = by_name_b.get(name)
        status_a = stage_a.status if stage_a else None
        status_b = stage_b.status if stage_b else None
        missing_a = stage_a is None
        missing_b = stage_b is None
        result.append(
            {
                "stage_order": order,
                "actor_name": name,
                "status_a": status_a,
                "status_b": status_b,
                "missing_a": missing_a,
                "missing_b": missing_b,
                "equal": (not missing_a and not missing_b and status_a == status_b),
            }
        )
    return result


def _job_summary(job: Job) -> dict[str, Any]:
    return {
        "id": job.id,
        "sample_name": job.sample_name,
        "status": job.status,
        "created_by": job.created_by,
    }


def build_job_diff(
    job_a: Job, job_b: Job, stages_a: list[JobStage], stages_b: list[JobStage]
) -> dict[str, Any]:
    metrics = build_metric_diffs(job_a, job_b)
    stages = build_stage_diffs(stages_a, stages_b)
    status_equal = job_a.status == job_b.status
    all_equal = (
        status_equal
        and all(m["equal"] for m in metrics)
        and all(s["equal"] for s in stages)
    )
    return {
        "job_a": _job_summary(job_a),
        "job_b": _job_summary(job_b),
        "status_equal": status_equal,
        "all_equal": all_equal,
        "metrics": metrics,
        "stages": stages,
    }
