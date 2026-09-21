"""Tests for the server-side job diff API and its role boundaries."""

GOOD_FASTQ = """@SEQ1
ACGTACGT
+
IIIIHHHH
@SEQ2
NNNNACGT
+
IIIIIIII
"""

BROKEN_FASTQ = """@SEQ1
ACGT
NOTPLUS
IIII
"""

# A second successful job with deliberately different metrics:
# reads=1, n_rate=0.0, mean_quality=40.0 (vs GOOD: 2, 0.25, 39.75).
GOOD_FASTQ_2 = """@SEQ3
ACGT
+
IIII
"""


def _submit(client, headers, text):
    resp = client.post(
        "/api/jobs", json={"fastqText": text}, headers=headers
    )
    assert resp.status_code == 201, resp.text
    # The create response is serialized before the pipeline background task
    # runs, so re-fetch the job (TestClient has completed the task by now).
    return _detail(client, headers, resp.json()["id"])


def _detail(client, headers, job_id):
    resp = client.get(f"/api/jobs/{job_id}", headers=headers)
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_auditor_can_diff_success_vs_failed_but_cannot_submit(
    client, bioops_headers, auditor_headers
):
    job_good = _submit(client, bioops_headers, GOOD_FASTQ)
    job_bad = _submit(client, bioops_headers, BROKEN_FASTQ)
    assert job_good["status"] == "success"
    assert job_bad["status"] == "failed"

    resp = client.get(
        "/api/jobs/diff",
        params={"a": job_good["id"], "b": job_bad["id"]},
        headers=auditor_headers,
    )
    assert resp.status_code == 200, resp.text
    diff = resp.json()

    # --- Verdict: statuses differ, overall diff not equal -------------------
    assert diff["status_equal"] is False
    assert diff["all_equal"] is False
    assert diff["job_a"]["id"] == job_good["id"]
    assert diff["job_b"]["id"] == job_bad["id"]

    # --- Three headline metrics, cross-checked against both detail payloads -
    detail_good = _detail(client, auditor_headers, job_good["id"])
    detail_bad = _detail(client, auditor_headers, job_bad["id"])
    assert detail_bad["metrics"] is None  # ParseActor failed → no metrics

    metrics = {m["key"]: m for m in diff["metrics"]}
    assert set(metrics) == {"reads", "mean_quality", "n_rate"}
    for key in ("reads", "mean_quality", "n_rate"):
        item = metrics[key]
        # Values come straight from the server-side diff and match the
        # per-job detail payloads (nothing recomputed in the browser).
        assert item["present_a"] is True
        assert item["value_a"] == detail_good["metrics"][key]
        assert item["present_b"] is False
        assert item["value_b"] is None
        assert item["both_missing"] is False
        assert item["delta"] is None
        assert item["equal"] is False

    assert metrics["reads"]["value_a"] == 2
    assert metrics["n_rate"]["value_a"] == 0.25

    # --- Four-stage status table, aligned with both detail stage lists ------
    stage_good = {s["actor_name"]: s["status"] for s in detail_good["stages"]}
    stage_bad = {s["actor_name"]: s["status"] for s in detail_bad["stages"]}
    assert [s["actor_name"] for s in diff["stages"]] == [
        "ParseActor",
        "QualityHistActor",
        "NContentActor",
        "ReportActor",
    ]
    for row in diff["stages"]:
        assert row["status_a"] == stage_good[row["actor_name"]]
        assert row["status_b"] == stage_bad[row["actor_name"]]
        assert row["missing_a"] is False
        assert row["missing_b"] is False
        assert row["equal"] is False
    assert stage_good == {
        "ParseActor": "success",
        "QualityHistActor": "success",
        "NContentActor": "success",
        "ReportActor": "success",
    }
    assert stage_bad == {
        "ParseActor": "failed",
        "QualityHistActor": "skipped",
        "NContentActor": "skipped",
        "ReportActor": "skipped",
    }

    # --- Auditor may read diffs but must NOT be able to submit jobs ---------
    forbidden = client.post(
        "/api/jobs", json={"fastqText": GOOD_FASTQ}, headers=auditor_headers
    )
    assert forbidden.status_code == 403


def test_two_identical_success_jobs_diff_as_equal(client, bioops_headers):
    job_one = _submit(client, bioops_headers, GOOD_FASTQ)
    job_two = _submit(client, bioops_headers, GOOD_FASTQ)

    resp = client.get(
        "/api/jobs/diff",
        params={"a": job_one["id"], "b": job_two["id"]},
        headers=bioops_headers,
    )
    assert resp.status_code == 200, resp.text
    diff = resp.json()

    assert diff["status_equal"] is True
    assert all(m["equal"] for m in diff["metrics"])
    assert all(s["equal"] for s in diff["stages"])
    assert diff["all_equal"] is True
    for item in diff["metrics"]:
        assert item["present_a"] is True and item["present_b"] is True
        assert item["delta"] == 0
    for row in diff["stages"]:
        assert row["status_a"] == row["status_b"] == "success"


def test_two_different_success_jobs_yield_signed_server_deltas(
    client, bioops_headers
):
    job_one = _submit(client, bioops_headers, GOOD_FASTQ)
    job_two = _submit(client, bioops_headers, GOOD_FASTQ_2)

    resp = client.get(
        "/api/jobs/diff",
        params={"a": job_one["id"], "b": job_two["id"]},
        headers=bioops_headers,
    )
    assert resp.status_code == 200, resp.text
    diff = resp.json()

    # Both succeeded, but the metric values genuinely differ.
    assert diff["status_equal"] is True
    assert diff["all_equal"] is False
    metrics = {m["key"]: m for m in diff["metrics"]}
    # deltas are computed server-side as A - B and carry sign
    assert metrics["reads"]["delta"] == 1
    assert metrics["mean_quality"]["delta"] == -0.25
    assert metrics["n_rate"]["delta"] == 0.25
    assert all(m["equal"] is False for m in metrics.values())
    assert all(s["equal"] for s in diff["stages"])  # stages identical: all success


def test_diff_requires_login(client, bioops_headers):
    job = _submit(client, bioops_headers, GOOD_FASTQ)
    resp = client.get("/api/jobs/diff", params={"a": job["id"], "b": job["id"]})
    assert resp.status_code == 401


def test_diff_rejects_same_job_and_missing_job(client, auditor_headers, bioops_headers):
    job = _submit(client, bioops_headers, GOOD_FASTQ)

    same = client.get(
        "/api/jobs/diff", params={"a": job["id"], "b": job["id"]},
        headers=auditor_headers,
    )
    assert same.status_code == 400

    missing = client.get(
        "/api/jobs/diff", params={"a": job["id"], "b": 999999},
        headers=auditor_headers,
    )
    assert missing.status_code == 404
