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


class JobDiffRequest(BaseModel):
    baseJobId: int
    targetJobId: int

    model_config = {"populate_by_name": True}


class DiffJobBrief(BaseModel):
    id: int
    sample_name: str
    status: str
    created_by: str
    error_message: str | None
    created_at: datetime
    finished_at: datetime | None


class MetricDiffOut(BaseModel):
    key: str
    label: str
    base_value: float | int | None
    target_value: float | int | None
    base_missing: bool
    target_missing: bool
    delta: float | int | None
    same: bool


class StageDiffOut(BaseModel):
    stage_order: int
    actor_name: str
    base_status: str | None
    target_status: str | None
    base_missing: bool
    target_missing: bool
    same: bool


class JobDiffOut(BaseModel):
    base: DiffJobBrief
    target: DiffJobBrief
    status_same: bool
    metrics_same: bool
    stages_same: bool
    metric_diffs: list[MetricDiffOut]
    stage_diffs: list[StageDiffOut]
