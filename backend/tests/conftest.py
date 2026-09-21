"""Test fixtures: file-backed sqlite + FastAPI TestClient.

DATABASE_URL must point at sqlite BEFORE app.config is imported, so this module
sets the env var at import time (pytest loads conftest before test modules).
"""

import os
import tempfile

import pytest
from fastapi.testclient import TestClient

_tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp_db.close()
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp_db.name}"

from app.database import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _create_schema():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)
    try:
        os.unlink(_tmp_db.name)
    except OSError:
        pass


@pytest.fixture
def db():
    session = SessionLocal()
    # Start each test from a clean slate.
    for table in reversed(Base.metadata.sorted_tables):
        session.execute(table.delete())
    session.commit()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def _token(client: TestClient, username: str, password: str) -> str:
    resp = client.post(
        "/api/auth/login", json={"username": username, "password": password}
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


@pytest.fixture
def auditor_headers(client):
    token = _token(client, "auditor", "audit123456")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def bioops_headers(client):
    token = _token(client, "bioops", "fastq123456")
    return {"Authorization": f"Bearer {token}"}
