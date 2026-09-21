"""Server-side diff logic for comparing two QC jobs.

The diff is computed HERE, in the backend — the frontend must never fetch two
job details and subtract metrics itself. The API returns:

- whether the two jobs' overall status is the same
- per-metric delta (target - base) for the three headline metrics, with an
  explicit missing flag when either side lacks the metric
- a row-per-actor status comparison for the four pipeline stages
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.models import Job, JobStage
from app.pipeline.runner import STAGE_NAMES

# (metric key in Job.metrics, API-facing Chinese label)
METRIC_KEYS: list[tuple[str, str]] = [
    ("reads", "reads 读段数"),
    ("mean_quality", "mean_quality 平均质量"),
    ("n_rate", "n_rate N 占比"),
]

_DELTA_EPSILON = 1e-9


@dataclass
class MetricDiff:
    key: str
    label: str
    base_value: float | int | None
    target_value: float | int | None
    base_missing: bool
    target_missing: bool
    delta: float | int | None
    same: bool


@dataclass
class StageDiff:
    stage_order: int
    actor_name: str
    base_status: str | None
    target_status: str | None
    base_missing: bool
    target_missing: bool
    same: bool


def _metric_value(metrics: dict[str, Any] | None, key: str) -> float | int | None:
    if not metrics:
        return None
    value = metrics.get(key)
    if value is None:
        return None
    return value


def _delta(base: float | int | None, target: float | int | None) -> float | int | None:
    if base is None or target is None:
        return None
    raw = target - base
    # Stored metrics are already rounded (reads int, mean_quality x.xxx,
    # n_rate x.xxxxxx); round the delta so it matches what the detail pages show.
    return round(raw, 6)


def _status_map(stages: list[JobStage]) -> dict[str, JobStage]:
    return {s.actor_name: s for s in stages}


def build_job_diff(
    base: Job,
    target: Job,
    base_stages: list[JobStage],
    target_stages: list[JobStage],
) -> dict[str, Any]:
    """Compute the full diff payload for two jobs."""
    metric_diffs: list[MetricDiff] = []
    for key, label in METRIC_KEYS:
        base_value = _metric_value(base.metrics, key)
        target_value = _metric_value(target.metrics, key)
        base_missing = base_value is None
        target_missing = target_value is None
        delta = _delta(base_value, target_value)
        if base_missing or target_missing:
            same = False
        else:
            same = abs(delta) <= _DELTA_EPSILON
        metric_diffs.append(
            MetricDiff(
                key=key,
                label=label,
                base_value=base_value,
                target_value=target_value,
                base_missing=base_missing,
                target_missing=target_missing,
                delta=delta,
                same=same,
            )
        )

    base_stage_map = _status_map(base_stages)
    target_stage_map = _status_map(target_stages)
    stage_diffs: list[StageDiff] = []
    for order, actor_name in enumerate(STAGE_NAMES):
        bs = base_stage_map.get(actor_name)
        ts = target_stage_map.get(actor_name)
        base_status = bs.status if bs else None
        target_status = ts.status if ts else None
        stage_diffs.append(
            StageDiff(
                stage_order=order,
                actor_name=actor_name,
                base_status=base_status,
                target_status=target_status,
                base_missing=base_status is None,
                target_missing=target_status is None,
                same=base_status == target_status,
            )
        )

    return {
        "base": _brief(base),
        "target": _brief(target),
        "status_same": base.status == target.status,
        "metrics_same": all(m.same and not m.base_missing and not m.target_missing for m in metric_diffs),
        "stages_same": all(s.same and not s.base_missing and not s.target_missing for s in stage_diffs),
        "metric_diffs": [m.__dict__ for m in metric_diffs],
        "stage_diffs": [s.__dict__ for s in stage_diffs],
    }


def _brief(job: Job) -> dict[str, Any]:
    return {
        "id": job.id,
        "sample_name": job.sample_name,
        "status": job.status,
        "created_by": job.created_by,
        "error_message": job.error_message,
        "created_at": job.created_at,
        "finished_at": job.finished_at,
    }


def load_jobs_for_diff(
    db: Session, base_id: int, target_id: int
) -> tuple[Job, list[JobStage], Job, list[JobStage]]:
    """Load both jobs with stages. Raises LookupError if either id is absent."""
    base = db.query(Job).filter(Job.id == base_id).first()
    if base is None:
        raise LookupError(base_id)
    target = db.query(Job).filter(Job.id == target_id).first()
    if target is None:
        raise LookupError(target_id)
    base_stages = (
        db.query(JobStage)
        .filter(JobStage.job_id == base_id)
        .order_by(JobStage.stage_order)
        .all()
    )
    target_stages = (
        db.query(JobStage)
        .filter(JobStage.job_id == target_id)
        .order_by(JobStage.stage_order)
        .all()
    )
    return base, base_stages, target, target_stages
