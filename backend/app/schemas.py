from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str
    role: str


class SampleOut(BaseModel):
    id: int
    name: str
    description: str
    is_broken: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class JobCreate(BaseModel):
    sampleId: int | None = None
    fastqText: str | None = Field(default=None, alias="fastqText")

    model_config = {"populate_by_name": True}


class StageOut(BaseModel):
    id: int
    actor_name: str
    stage_order: int
    status: str
    message: str | None
    started_at: datetime | None
    finished_at: datetime | None

    model_config = {"from_attributes": True}


class JobOut(BaseModel):
    id: int
    sample_id: int | None
    sample_name: str
    status: str
    created_by: str
    metrics: dict[str, Any] | None
    error_message: str | None
    created_at: datetime
    finished_at: datetime | None
    stages: list[StageOut] = []

    model_config = {"from_attributes": True}


class JobListItem(BaseModel):
    id: int
    sample_id: int | None
    sample_name: str
    status: str
    created_by: str
    metrics: dict[str, Any] | None
    error_message: str | None
    created_at: datetime
    finished_at: datetime | None

    model_config = {"from_attributes": True}


class HealthOut(BaseModel):
    status: str
    service: str


class DiffJobRef(BaseModel):
    id: int
    sample_name: str
    status: str
    created_by: str


class MetricDiffItem(BaseModel):
    key: str
    label: str
    value_a: Any | None
    value_b: Any | None
    present_a: bool
    present_b: bool
    both_missing: bool
    delta: int | float | None
    equal: bool


class StageDiffItem(BaseModel):
    stage_order: int
    actor_name: str
    status_a: str | None
    status_b: str | None
    missing_a: bool
    missing_b: bool
    equal: bool


class JobDiffOut(BaseModel):
    job_a: DiffJobRef
    job_b: DiffJobRef
    status_equal: bool
    all_equal: bool
    metrics: list[MetricDiffItem]
    stages: list[StageDiffItem]
