"""KPI Engine — executes structured KPI plans against a Pandas DataFrame.

The plan-to-Pandas approach: the LLM outputs a structured JSON plan
(aggregation, filters, grouping, time window). This module translates
that plan into deterministic Pandas operations — no eval() or exec().
"""
from __future__ import annotations

import logging
from typing import Any, Optional

import pandas as pd

from app.models import KPI, KPIBreakdownEntry, KPIFilter, KPIPlan

logger = logging.getLogger(__name__)

_OPERATORS = {
    "eq": lambda s, v: s == v,
    "ne": lambda s, v: s != v,
    "gt": lambda s, v: s > v,
    "lt": lambda s, v: s < v,
    "gte": lambda s, v: s >= v,
    "lte": lambda s, v: s <= v,
    "in": lambda s, v: s.isin(v if isinstance(v, list) else [v]),
}


def _apply_filters(df: pd.DataFrame, filters: list[KPIFilter]) -> pd.DataFrame:
    for f in filters:
        if f.column not in df.columns:
            logger.warning("Filter column %r not found — skipping", f.column)
            continue
        op_fn = _OPERATORS.get(f.operator)
        if op_fn is None:
            logger.warning("Unknown filter operator %r — skipping", f.operator)
            continue
        mask = op_fn(df[f.column], f.value)
        df = df[mask]
    return df


def _apply_time_window(df: pd.DataFrame, plan: KPIPlan) -> pd.DataFrame:
    if not plan.time_column or plan.time_window_days is None:
        return df
    if plan.time_column not in df.columns:
        logger.warning("Time column %r not found — skipping window", plan.time_column)
        return df
    try:
        df = df.copy()
        df[plan.time_column] = pd.to_datetime(df[plan.time_column], errors="coerce")
        cutoff = df[plan.time_column].max() - pd.Timedelta(days=plan.time_window_days)
        df = df[df[plan.time_column] >= cutoff]
    except Exception as exc:
        logger.warning("Could not apply time window: %s", exc)
    return df


def _scalar(val: Any) -> Optional[float]:
    if val is None:
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def _mean_date_diff_days(df: pd.DataFrame, start_col: str, end_col: str) -> Optional[float]:
    if start_col not in df.columns or end_col not in df.columns:
        return None
    try:
        tmp = df.copy()
        tmp[start_col] = pd.to_datetime(tmp[start_col], errors="coerce")
        tmp[end_col] = pd.to_datetime(tmp[end_col], errors="coerce")
        diffs = (tmp[end_col] - tmp[start_col]).dt.total_seconds() / 86400.0
        diffs = diffs.dropna()
        if diffs.empty:
            return None
        return _scalar(diffs.mean())
    except Exception as exc:
        logger.warning("mean date diff computation failed: %s", exc)
        return None


def _numeric_or_count_distinct(series: pd.Series) -> Optional[float]:
    numeric = pd.to_numeric(series, errors="coerce")
    if numeric.notna().any():
        return _scalar(numeric.sum())
    return _scalar(series.nunique())


def _group_key_to_label(key: Any) -> str:
    if isinstance(key, tuple):
        return " / ".join(str(part) for part in key)
    return str(key)


def _grouped_metric_values(df: pd.DataFrame, plan: KPIPlan) -> Optional[pd.Series]:
    group_cols = [c for c in plan.group_by if c in df.columns]
    if not group_cols:
        return None

    metric = plan.metric
    grouped = df.groupby(group_cols, dropna=False)

    if metric == "count":
        return grouped.size().astype(float)

    if metric == "count_distinct":
        if not plan.column or plan.column not in df.columns:
            return None
        return grouped[plan.column].nunique().astype(float)

    if metric == "sum":
        if not plan.column or plan.column not in df.columns:
            return None
        return grouped[plan.column].apply(lambda s: pd.to_numeric(s, errors="coerce").sum())

    if metric == "mean":
        if plan.column and plan.column in df.columns:
            return grouped[plan.column].apply(lambda s: pd.to_numeric(s, errors="coerce").mean())
        if plan.numerator_column and plan.denominator_column:
            return grouped.apply(
                lambda g: _mean_date_diff_days(g, plan.denominator_column, plan.numerator_column)
            )
        return None

    if metric in {"ratio", "growth_rate", "mean_days_between"}:
        plan_no_group = plan.model_copy(update={"group_by": []})
        return grouped.apply(lambda g: execute_plan(g, plan_no_group))

    return None


def _grouped_aggregate(df: pd.DataFrame, plan: KPIPlan) -> Optional[float]:
    values = _grouped_metric_values(df, plan)
    if values is None or values.empty:
        return None
    series = pd.to_numeric(values, errors="coerce").dropna()
    if series.empty:
        return None
    return _scalar(series.max())


def get_group_label(df: pd.DataFrame, plan: KPIPlan) -> Optional[str]:
    values = _grouped_metric_values(df, plan)
    if values is None or values.empty:
        return None
    series = pd.to_numeric(values, errors="coerce").dropna()
    if series.empty:
        return None
    return _group_key_to_label(series.idxmax())


def build_breakdown(df: pd.DataFrame, plan: KPIPlan) -> Optional[list[KPIBreakdownEntry]]:
    df = _apply_time_window(df, plan)
    df = _apply_filters(df, plan.filters)
    if df.empty:
        return None

    values = _grouped_metric_values(df, plan)
    if values is None or values.empty:
        return None

    series = pd.to_numeric(values, errors="coerce").dropna()
    if series.empty:
        return None

    total = series.sum()
    breakdown: list[KPIBreakdownEntry] = []
    for key, val in series.sort_values(ascending=False).items():
        pct = None
        if total and total != 0:
            pct = float(val / total * 100)
        breakdown.append(
            KPIBreakdownEntry(
                label=_group_key_to_label(key),
                value=float(val),
                pct=pct,
            )
        )
    return breakdown


def execute_plan(df: pd.DataFrame, plan: KPIPlan) -> Optional[float]:
    """Execute a KPIPlan against a DataFrame and return a scalar result."""
    df = _apply_time_window(df, plan)
    df = _apply_filters(df, plan.filters)

    if df.empty:
        logger.warning("Plan returned empty dataframe metric=%s", plan.metric)
        return None

    if plan.group_by:
        grouped_value = _grouped_aggregate(df, plan)
        if grouped_value is not None:
            return grouped_value

    metric = plan.metric

    if metric == "count":
        return float(len(df))

    if metric == "count_distinct":
        if not plan.column or plan.column not in df.columns:
            logger.warning("count_distinct missing column=%s", plan.column)
            return None
        return float(df[plan.column].nunique())

    if metric == "sum":
        if not plan.column or plan.column not in df.columns:
            logger.warning("sum missing column=%s", plan.column)
            return None
        return _scalar(pd.to_numeric(df[plan.column], errors="coerce").sum())

    if metric == "mean":
        if plan.column and plan.column in df.columns:
            return _scalar(pd.to_numeric(df[plan.column], errors="coerce").mean())
        if plan.numerator_column and plan.denominator_column:
            return _mean_date_diff_days(df, plan.denominator_column, plan.numerator_column)
        logger.warning("mean missing column or date diff inputs")
        return None

    if metric == "ratio":
        num_col = plan.numerator_column
        den_col = plan.denominator_column
        if not num_col or not den_col:
            logger.warning("ratio missing numerator or denominator")
            return None
        if num_col not in df.columns or den_col not in df.columns:
            logger.warning("ratio missing columns numerator=%s denominator=%s", num_col, den_col)
            return None
        num = _numeric_or_count_distinct(df[num_col])
        den = _numeric_or_count_distinct(df[den_col])
        if den == 0:
            logger.warning("ratio zero denominator")
            return None
        return _scalar(num / den)

    if metric == "mean_days_between":
        if not plan.numerator_column or not plan.denominator_column:
            logger.warning("mean_days_between missing columns")
            return None
        return _mean_date_diff_days(df, plan.denominator_column, plan.numerator_column)

    if metric == "growth_rate":
        if not plan.column or plan.column not in df.columns:
            return None
        if not plan.time_column or plan.time_column not in df.columns:
            return None
        try:
            tmp = df.copy()
            tmp[plan.time_column] = pd.to_datetime(tmp[plan.time_column], errors="coerce")
            tmp = tmp.sort_values(plan.time_column)
            tmp["_val"] = pd.to_numeric(tmp[plan.column], errors="coerce")
            first = tmp["_val"].iloc[0]
            last = tmp["_val"].iloc[-1]
            if first == 0:
                return None
            return _scalar((last - first) / abs(first))
        except Exception as exc:
            logger.warning("growth_rate computation failed: %s", exc)
            return None

    logger.warning("Unknown metric %r", metric)
    return None


def compute_kpis(df: pd.DataFrame, kpis: list[KPI]) -> list[KPI]:
    """Compute values for a list of KPIs against a DataFrame.

    Returns the same KPI objects with value and computed_at populated.
    """
    from datetime import datetime, timezone

    updated = []
    for kpi in kpis:
        breakdown = None
        try:
            value = execute_plan(df, kpi.plan)
            if kpi.plan.group_by:
                breakdown = build_breakdown(df, kpi.plan)
                if breakdown and kpi.plan.metric in {"sum", "count"}:
                    value = sum(b.value for b in breakdown)
        except Exception as exc:
            logger.error("KPI %s computation error: %s", kpi.kpi_id, exc)
            value = None
        updated.append(
            kpi.model_copy(
                update={
                    "value": value,
                    "value_breakdown": breakdown,
                    "computed_at": datetime.now(timezone.utc).isoformat(),
                }
            )
        )
    return updated
