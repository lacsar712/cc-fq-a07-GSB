"""Tests for server-side job diff: pure function + API auth/behavior."""

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api import get_current_user
from app.database import Base, get_db
from app.diff import build_job_diff
from app.main import app
from app.models import Job
from app.pipeline.runner import STAGE_NAMES, create_job_stages


def _job(job_id, status, metrics, error=None):
    return SimpleNamespace(
        id=job_id,
        sample_name=f"sample-{job_id}",
        status=status,
        created_by="bioops",
        metrics=metrics,
        error_message=error,
        created_at=None,
        finished_at=None,
    )


def _stages(spec):
    """spec: dict actor_name -> status, in pipeline order; missing => absent."""
    return [
        SimpleNamespace(actor_name=name, status=spec[name], stage_order=i)
        for i, name in enumerate(STAGE_NAMES)
        if name in spec
    ]


SUCCESS_STAGES = {name: "success" for name in STAGE_NAMES}
FAILED_STAGES = {
    "ParseActor": "failed",
    "QualityHistActor": "skipped",
    "NContentActor": "skipped",
    "ReportActor": "skipped",
}
GOOD_METRICS = {"reads": 3, "mean_quality": 33.5, "n_rate": 0.020833}


def test_diff_success_vs_parse_failure():
    base = _job(1, "success", GOOD_METRICS)
    target = _job(2, "failed", None, error="第 3 行分隔符必须以 + 开头")
    result = build_job_diff(base, target, _stages(SUCCESS_STAGES), _stages(FAILED_STAGES))

    assert result["status_same"] is False
    assert result["metrics_same"] is False
    assert result["stages_same"] is False

    for m in result["metric_diffs"]:
        assert m["target_missing"] is True
        assert m["base_missing"] is False
        assert m["delta"] is None
        assert m["same"] is False

    by_actor = {s["actor_name"]: s for s in result["stage_diffs"]}
    assert by_actor["ParseActor"]["base_status"] == "success"
    assert by_actor["ParseActor"]["target_status"] == "failed"
    assert by_actor["ParseActor"]["same"] is False
    assert by_actor["QualityHistActor"]["target_status"] == "skipped"
    assert by_actor["QualityHistActor"]["same"] is False
    assert by_actor["ReportActor"]["same"] is False


def test_diff_identical_jobs():
    base = _job(1, "success", dict(GOOD_METRICS))
    target = _job(2, "success", dict(GOOD_METRICS))
    result = build_job_diff(base, target, _stages(SUCCESS_STAGES), _stages(SUCCESS_STAGES))

    assert result["status_same"] is True
    assert result["metrics_same"] is True
    assert result["stages_same"] is True
    assert {m["key"]: m["delta"] for m in result["metric_diffs"]} == {
        "reads": 0,
        "mean_quality": 0,
        "n_rate": 0,
    }
    assert all(s["same"] for s in result["stage_diffs"])


def test_diff_metric_deltas_and_partial_missing():
    # base lacks n_rate (e.g. failed at NContent); target fully succeeds
    base = _job(
        1,
        "failed",
        {"reads": 3, "mean_quality": 33.5},  # n_rate intentionally absent
    )
    target = _job(2, "success", {"reads": 5, "mean_quality": 34.0, "n_rate": 0.1})
    result = build_job_diff(base, target, _stages(SUCCESS_STAGES), _stages(SUCCESS_STAGES))

    metrics = {m["key"]: m for m in result["metric_diffs"]}
    assert metrics["reads"]["delta"] == 2
    assert metrics["reads"]["same"] is False
    assert metrics["mean_quality"]["delta"] == pytest.approx(0.5)
    n_rate = metrics["n_rate"]
    assert n_rate["base_missing"] is True
    assert n_rate["target_missing"] is False
    assert n_rate["delta"] is None
    assert n_rate["same"] is False


@pytest.fixture()
def client_with_db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestSession = sessionmaker(bind=engine)

    def override_db():
        db = TestSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_db
    client = TestClient(app)
    try:
        yield client, TestSession
    finally:
        app.dependency_overrides.clear()


def _insert_job(db, status, metrics=None, stages_spec=None):
    job = Job(
        sample_name="demo",
        status=status,
        created_by="bioops",
        metrics=metrics,
        fastq_snapshot="@x\nACGT\n+\nIIII\n",
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    for stage in create_job_stages(db, job.id):
        if stages_spec and stage.actor_name in stages_spec:
            stage.status = stages_spec[stage.actor_name]
    db.commit()
    return job.id


def test_auditor_can_diff_but_cannot_submit(client_with_db):
    client, TestSession = client_with_db
    app.dependency_overrides[get_current_user] = lambda: {
        "username": "auditor",
        "role": "auditor",
    }

    db = TestSession()
    good_id = _insert_job(db, "success", GOOD_METRICS, SUCCESS_STAGES)
    bad_id = _insert_job(db, "failed", None, FAILED_STAGES)
    db.close()

    # Auditor may use the diff endpoint...
    resp = client.post("/api/jobs/diff", json={"baseJobId": good_id, "targetJobId": bad_id})
    assert resp.status_code == 200
    body = resp.json()
    assert body["status_same"] is False
    assert len(body["stage_diffs"]) == 4
    assert all(m["target_missing"] for m in body["metric_diffs"])

    # ...but diff access must not double as a way to submit a new job.
    forbidden = client.post("/api/jobs", json={"fastqText": "@x\nACGT\n+\nIIII\n"})
    assert forbidden.status_code == 403


def test_diff_endpoint_validates_inputs(client_with_db):
    client, TestSession = client_with_db
    app.dependency_overrides[get_current_user] = lambda: {
        "username": "bioops",
        "role": "bioops",
    }

    db = TestSession()
    good_id = _insert_job(db, "success", GOOD_METRICS, SUCCESS_STAGES)
    db.close()

    same_job = client.post("/api/jobs/diff", json={"baseJobId": good_id, "targetJobId": good_id})
    assert same_job.status_code == 400

    missing = client.post("/api/jobs/diff", json={"baseJobId": good_id, "targetJobId": 9999})
    assert missing.status_code == 404


def test_diff_requires_authentication(client_with_db):
    client, _ = client_with_db
    resp = client.post("/api/jobs/diff", json={"baseJobId": 1, "targetJobId": 2})
    assert resp.status_code == 401
