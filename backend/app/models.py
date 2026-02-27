"""Pydantic domain models for Argus."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class JobStatus(str, Enum):
    queued = "queued"
    running = "running"
    awaiting_kpi_approval = "awaiting_kpi_approval"
    awaiting_recommendation_approval = "awaiting_recommendation_approval"
    complete = "complete"
    failed = "failed"


class JobStage(str, Enum):
    profile = "profile"
    generate_kpis = "generate_kpis"
    compute_kpis = "compute_kpis"
    generate_report = "generate_report"


class KPIStatus(str, Enum):
    proposed = "proposed"
    approved = "approved"
    rejected = "rejected"


# ---------------------------------------------------------------------------
# Project
# ---------------------------------------------------------------------------

class ProjectCreate(BaseModel):
    name: str
    business_description: str


class Project(BaseModel):
    project_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    business_description: str
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    status: str = "active"


# ---------------------------------------------------------------------------
# Dataset
# ---------------------------------------------------------------------------

class DatasetCreate(BaseModel):
    project_id: str
    filename: str


class ColumnProfile(BaseModel):
    name: str
    dtype: str
    null_count: int
    null_pct: float
    unique_count: int
    sample_values: list[Any]
    is_date: bool = False
    is_id: bool = False
    min: Optional[Any] = None
    max: Optional[Any] = None
    mean: Optional[float] = None


class DatasetProfile(BaseModel):
    row_count: int
    column_count: int
    columns: list[ColumnProfile]
    potential_join_keys: list[str] = []
    date_columns: list[str] = []


class Dataset(BaseModel):
    dataset_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    project_id: str
    filename: str
    s3_key: str = ""
    profile: Optional[DatasetProfile] = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# ---------------------------------------------------------------------------
# KPI
# ---------------------------------------------------------------------------

class KPIFilter(BaseModel):
    column: str
    operator: str  # eq, ne, gt, lt, gte, lte, in
    value: Any


class KPIPlan(BaseModel):
    """Structured computation plan (plan-to-Pandas approach)."""
    metric: str  # sum, mean, count, count_distinct, ratio, growth_rate
    column: Optional[str] = None
    numerator_column: Optional[str] = None
    denominator_column: Optional[str] = None
    filters: list[KPIFilter] = []
    group_by: list[str] = []
    time_column: Optional[str] = None
    time_window_days: Optional[int] = None


class KPIProposal(BaseModel):
    name: str
    description: str
    rationale: str
    formula: str
    plan: KPIPlan
    target: Optional[float] = None
    unit: Optional[str] = None


class KPIBreakdownEntry(BaseModel):
    label: str
    value: float
    pct: Optional[float] = None


class KPI(BaseModel):
    kpi_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    project_id: str
    name: str
    description: str
    rationale: str
    formula: str
    plan: KPIPlan
    target: Optional[float] = None
    unit: Optional[str] = None
    status: KPIStatus = KPIStatus.proposed
    value: Optional[float] = None
    value_label: Optional[str] = None
    value_breakdown: Optional[list[KPIBreakdownEntry]] = None
    computed_at: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class KPIApprovalRequest(BaseModel):
    approvals: dict[str, KPIStatus]  # kpi_id -> approved/rejected


class CustomKPIRequest(BaseModel):
    request: str


# ---------------------------------------------------------------------------
# Job
# ---------------------------------------------------------------------------

class Job(BaseModel):
    job_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    project_id: str
    stage: JobStage
    status: JobStatus = JobStatus.queued
    error: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class JobMessage(BaseModel):
    job_id: str
    project_id: str
    stage: JobStage
    dataset_id: Optional[str] = None


# ---------------------------------------------------------------------------
# Advisory Report
# ---------------------------------------------------------------------------

class RiskSignal(BaseModel):
    title: str
    description: str
    severity: str  # low, medium, high


class ComplianceNote(BaseModel):
    regulation: str
    observation: str
    action_required: bool


class Forecast(BaseModel):
    kpi_name: str
    horizon_days: int
    trend: str  # up, down, flat
    narrative: str


class Recommendation(BaseModel):
    title: str
    description: str
    requires_approval: bool
    approved: Optional[bool] = None


class AdvisoryReport(BaseModel):
    report_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    project_id: str
    business_model_summary: str
    risks: list[RiskSignal]
    compliance_notes: list[ComplianceNote]
    forecasts: list[Forecast]
    recommendations: list[Recommendation]
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    s3_key: str = ""


class RecommendationApprovalRequest(BaseModel):
    approvals: dict[int, bool]  # index -> approved


# ---------------------------------------------------------------------------
# Dashboard Spec
# ---------------------------------------------------------------------------

class DashboardWidgetType(str, Enum):
    kpi_card = "kpi_card"
    bar = "bar"
    line = "line"
    area = "area"
    pie = "pie"
    table = "table"


class DashboardWidget(BaseModel):
    widget_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    type: DashboardWidgetType
    title: str
    description: Optional[str] = None
    kpi_ids: list[str] = []
    size: str = "md"  # sm, md, lg, xl
    section: Optional[str] = None
    value_key: Optional[str] = None  # value or pct


class DashboardSpec(BaseModel):
    dashboard_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    project_id: str
    title: str
    summary: Optional[str] = None
    widgets: list[DashboardWidget]
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
