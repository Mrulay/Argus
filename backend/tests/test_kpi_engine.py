"""Tests for the KPI engine."""
from __future__ import annotations

import pandas as pd
import pytest

from app.models import KPI, KPIFilter, KPIPlan, KPIStatus
from app.services.kpi_engine import execute_plan, compute_kpis, get_group_label, build_breakdown


def _sales_df() -> pd.DataFrame:
    return pd.DataFrame({
        "order_id": range(10),
        "revenue": [100, 200, 150, 300, 250, 400, 50, 175, 325, 275],
        "category": ["A", "B", "A", "B", "A", "B", "A", "B", "A", "B"],
        "date": pd.to_datetime([
            "2024-01-01", "2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05",
            "2024-01-06", "2024-01-07", "2024-01-08", "2024-01-09", "2024-01-10",
        ]),
        "cost": [50, 100, 75, 150, 125, 200, 25, 87, 160, 137],
    })


class TestExecutePlan:
    def test_count(self):
        df = _sales_df()
        plan = KPIPlan(metric="count")
        assert execute_plan(df, plan) == 10.0

    def test_sum(self):
        df = _sales_df()
        plan = KPIPlan(metric="sum", column="revenue")
        result = execute_plan(df, plan)
        assert result == pytest.approx(2225.0)

    def test_mean(self):
        df = _sales_df()
        plan = KPIPlan(metric="mean", column="revenue")
        result = execute_plan(df, plan)
        assert result == pytest.approx(222.5)

    def test_count_distinct(self):
        df = _sales_df()
        plan = KPIPlan(metric="count_distinct", column="category")
        assert execute_plan(df, plan) == 2.0

    def test_ratio(self):
        df = _sales_df()
        plan = KPIPlan(metric="ratio", numerator_column="cost", denominator_column="revenue")
        result = execute_plan(df, plan)
        # total cost = 1109, total revenue = 2225
        assert result == pytest.approx(1109 / 2225, rel=1e-3)

    def test_ratio_count_distinct_denominator(self):
        df = _sales_df()
        plan = KPIPlan(metric="ratio", numerator_column="revenue", denominator_column="order_id")
        result = execute_plan(df, plan)
        # denominator falls back to count distinct order_id
        assert result == pytest.approx(2225 / 10, rel=1e-3)

    def test_growth_rate(self):
        df = pd.DataFrame({
            "date": pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-03"]),
            "revenue": [100.0, 150.0, 200.0],
        })
        plan = KPIPlan(metric="growth_rate", column="revenue", time_column="date")
        result = execute_plan(df, plan)
        assert result == pytest.approx(1.0)  # (200-100)/100 = 1.0

    def test_filter_eq(self):
        df = _sales_df()
        plan = KPIPlan(
            metric="sum",
            column="revenue",
            filters=[KPIFilter(column="category", operator="eq", value="A")],
        )
        result = execute_plan(df, plan)
        # Category A: 100+150+250+50+325 = 875
        assert result == pytest.approx(875.0)

    def test_filter_gt(self):
        df = _sales_df()
        plan = KPIPlan(
            metric="count",
            filters=[KPIFilter(column="revenue", operator="gt", value=200)],
        )
        result = execute_plan(df, plan)
        assert result == 5.0

    def test_time_window(self):
        df = _sales_df()
        plan = KPIPlan(
            metric="count",
            time_column="date",
            time_window_days=3,
        )
        result = execute_plan(df, plan)
        # max date = Jan 10; cutoff = Jan 7; rows >= Jan 7 → Jan 7, 8, 9, 10 = 4 rows
        assert result == 4.0

    def test_unknown_column_returns_none(self):
        df = _sales_df()
        plan = KPIPlan(metric="sum", column="nonexistent")
        assert execute_plan(df, plan) is None

    def test_group_by_top_label(self):
        df = _sales_df()
        plan = KPIPlan(metric="sum", column="revenue", group_by=["category"])
        label = get_group_label(df, plan)
        assert label in {"A", "B"}

    def test_group_by_breakdown(self):
        df = _sales_df()
        plan = KPIPlan(metric="sum", column="revenue", group_by=["category"])
        breakdown = build_breakdown(df, plan)
        assert breakdown is not None
        labels = {b.label for b in breakdown}
        assert labels == {"A", "B"}

    def test_empty_dataframe_returns_none(self):
        df = pd.DataFrame({"revenue": []})
        plan = KPIPlan(metric="sum", column="revenue")
        assert execute_plan(df, plan) is None

    def test_ratio_zero_denominator(self):
        df = pd.DataFrame({"a": [1.0, 2.0], "b": [0.0, 0.0]})
        plan = KPIPlan(metric="ratio", numerator_column="a", denominator_column="b")
        assert execute_plan(df, plan) is None

    def test_unknown_metric(self):
        df = _sales_df()
        plan = KPIPlan(metric="median", column="revenue")  # type: ignore[arg-type]
        assert execute_plan(df, plan) is None


class TestComputeKPIs:
    def test_compute_kpis_updates_value(self):
        df = _sales_df()
        kpi = KPI(
            project_id="proj-1",
            name="Total Revenue",
            description="Sum of all revenue",
            rationale="Core business metric",
            formula="SUM(revenue)",
            plan=KPIPlan(metric="sum", column="revenue"),
            status=KPIStatus.approved,
        )
        results = compute_kpis(df, [kpi])
        assert len(results) == 1
        assert results[0].value == pytest.approx(2225.0)
        assert results[0].computed_at is not None

    def test_compute_kpis_breakdown(self):
        df = _sales_df()
        kpi = KPI(
            project_id="proj-1",
            name="Revenue Mix",
            description="Revenue by category",
            rationale="Mix",
            formula="SUM(revenue) by category",
            plan=KPIPlan(metric="sum", column="revenue", group_by=["category"]),
            status=KPIStatus.approved,
        )
        results = compute_kpis(df, [kpi])
        assert results[0].value_breakdown is not None

    def test_compute_kpis_multiple(self):
        df = _sales_df()
        kpis = [
            KPI(
                project_id="proj-1",
                name="Total Revenue",
                description="Sum revenue",
                rationale="r",
                formula="SUM(revenue)",
                plan=KPIPlan(metric="sum", column="revenue"),
                status=KPIStatus.approved,
            ),
            KPI(
                project_id="proj-1",
                name="Order Count",
                description="Count orders",
                rationale="r",
                formula="COUNT(*)",
                plan=KPIPlan(metric="count"),
                status=KPIStatus.approved,
            ),
        ]
        results = compute_kpis(df, kpis)
        assert len(results) == 2
        assert results[0].value == pytest.approx(2225.0)
        assert results[1].value == 10.0
