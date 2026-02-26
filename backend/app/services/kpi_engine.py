"""KPI Engine — executes structured KPI plans against a Pandas DataFrame.

The plan-to-Pandas approach: the LLM outputs a structured JSON plan
(aggregation, filters, grouping, time window). This module translates
that plan into deterministic Pandas operations — no eval() or exec().
"""
from __future__ import annotations

import logging
from typing import Any, Optional

import pandas as pd

from app.models import KPI, KPIFilter, KPIPlan

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


def execute_plan(df: pd.DataFrame, plan: KPIPlan) -> Optional[float]:
    """Execute a KPIPlan against a DataFrame and return a scalar result."""
    df = _apply_time_window(df, plan)
    df = _apply_filters(df, plan.filters)

    if df.empty:
        return None

    metric = plan.metric

    if metric == "count":
        return float(len(df))

    if metric == "count_distinct":
        if not plan.column or plan.column not in df.columns:
            return None
        return float(df[plan.column].nunique())

    if metric == "sum":
        if not plan.column or plan.column not in df.columns:
            return None
        return _scalar(pd.to_numeric(df[plan.column], errors="coerce").sum())

    if metric == "mean":
        if not plan.column or plan.column not in df.columns:
            return None
        return _scalar(pd.to_numeric(df[plan.column], errors="coerce").mean())

    if metric == "ratio":
        num_col = plan.numerator_column
        den_col = plan.denominator_column
        if not num_col or not den_col:
            return None
        if num_col not in df.columns or den_col not in df.columns:
            return None
        num = pd.to_numeric(df[num_col], errors="coerce").sum()
        den = pd.to_numeric(df[den_col], errors="coerce").sum()
        if den == 0:
            return None
        return _scalar(num / den)

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
        try:
            value = execute_plan(df, kpi.plan)
        except Exception as exc:
            logger.error("KPI %s computation error: %s", kpi.kpi_id, exc)
            value = None
        updated.append(
            kpi.model_copy(
                update={
                    "value": value,
                    "computed_at": datetime.now(timezone.utc).isoformat(),
                }
            )
        )
    return updated
