"""Tests for Pydantic domain models."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.models import (
    AdvisoryReport,
    Dataset,
    Forecast,
    Job,
    JobStage,
    JobStatus,
    KPI,
    KPIFilter,
    KPIPlan,
    KPIStatus,
    Project,
    Recommendation,
    RecommendationApprovalRequest,
    RiskSignal,
)


class TestProject:
    def test_default_fields(self):
        p = Project(name="Test Co", business_description="Sells widgets")
        assert p.project_id
        assert p.created_at
        assert p.status == "active"

    def test_serialization_roundtrip(self):
        p = Project(name="Acme", business_description="B2B SaaS")
        p2 = Project(**p.model_dump())
        assert p2.project_id == p.project_id


class TestKPIPlan:
    def test_defaults(self):
        plan = KPIPlan(metric="count")
        assert plan.filters == []
        assert plan.group_by == []

    def test_with_filter(self):
        f = KPIFilter(column="status", operator="eq", value="active")
        plan = KPIPlan(metric="count", filters=[f])
        assert len(plan.filters) == 1

    def test_invalid_filter_operator_is_stored(self):
        # Model does not restrict operator values; engine handles unknown ops
        f = KPIFilter(column="x", operator="between", value=5)
        assert f.operator == "between"


class TestKPI:
    def test_default_status(self):
        kpi = KPI(
            project_id="proj-1",
            name="Revenue",
            description="Total revenue",
            rationale="Core metric",
            formula="SUM(revenue)",
            plan=KPIPlan(metric="sum", column="revenue"),
        )
        assert kpi.status == KPIStatus.proposed
        assert kpi.value is None
        assert kpi.computed_at is None

    def test_approved_status(self):
        kpi = KPI(
            project_id="proj-1",
            name="Revenue",
            description="d",
            rationale="r",
            formula="SUM(revenue)",
            plan=KPIPlan(metric="sum", column="revenue"),
            status=KPIStatus.approved,
        )
        assert kpi.status == KPIStatus.approved


class TestJob:
    def test_default_status(self):
        job = Job(project_id="proj-1", stage=JobStage.profile)
        assert job.status == JobStatus.queued
        assert job.error is None

    def test_all_stages_valid(self):
        for stage in JobStage:
            job = Job(project_id="proj-1", stage=stage)
            assert job.stage == stage


class TestAdvisoryReport:
    def test_empty_report(self):
        r = AdvisoryReport(
            project_id="proj-1",
            business_model_summary="SaaS company",
            risks=[],
            compliance_notes=[],
            forecasts=[],
            recommendations=[],
        )
        assert r.report_id
        assert r.created_at

    def test_risk_signal(self):
        risk = RiskSignal(title="High churn", description="Churn rate elevated", severity="high")
        assert risk.severity == "high"

    def test_forecast(self):
        f = Forecast(kpi_name="Revenue", horizon_days=30, trend="up", narrative="Growth expected")
        assert f.trend == "up"

    def test_recommendation_approval(self):
        rec = Recommendation(
            title="Expand to new market",
            description="Enter APAC",
            requires_approval=True,
        )
        assert rec.approved is None
        rec2 = rec.model_copy(update={"approved": True})
        assert rec2.approved is True


class TestRecommendationApprovalRequest:
    def test_approvals_dict(self):
        req = RecommendationApprovalRequest(approvals={0: True, 1: False})
        assert req.approvals[0] is True
        assert req.approvals[1] is False
