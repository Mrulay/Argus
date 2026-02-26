"""Data Profiler — detects columns, types, dates, IDs, missingness, joinability."""
from __future__ import annotations

import io
import re
from typing import Any

import pandas as pd

from app.models import ColumnProfile, DatasetProfile

_DATE_PATTERNS = re.compile(
    r"(date|time|timestamp|created|updated|at|dt|day|month|year|period)",
    re.IGNORECASE,
)
_ID_PATTERNS = re.compile(r"(^id$|_id$|_key$|uuid|guid)", re.IGNORECASE)
_NUMERIC_THRESHOLD = 0.8  # fraction of non-null values that parse as numeric


def _infer_is_date(series: pd.Series, name: str) -> bool:
    if _DATE_PATTERNS.search(name):
        return True
    if series.dtype == "object":
        sample = series.dropna().head(20)
        parsed = 0
        for val in sample:
            try:
                pd.to_datetime(str(val))
                parsed += 1
            except Exception:
                pass
        return parsed / max(len(sample), 1) >= 0.7
    return pd.api.types.is_datetime64_any_dtype(series)


def _infer_is_id(series: pd.Series, name: str) -> bool:
    if _ID_PATTERNS.search(name):
        return True
    n = len(series.dropna())
    if n == 0:
        return False
    return series.nunique() / n >= 0.95


def _safe_stat(val: Any) -> Any:
    """Convert numpy scalars to plain Python types."""
    try:
        import numpy as np  # noqa: F401
        if hasattr(val, "item"):
            return val.item()
    except ImportError:
        pass
    return val


def profile_dataframe(df: pd.DataFrame) -> DatasetProfile:
    columns: list[ColumnProfile] = []
    date_columns: list[str] = []
    potential_join_keys: list[str] = []

    for col in df.columns:
        series = df[col]
        null_count = int(series.isna().sum())
        null_pct = round(null_count / len(df) * 100, 2) if len(df) > 0 else 0.0
        unique_count = int(series.nunique())
        sample_values = [
            _safe_stat(v) for v in series.dropna().head(5).tolist()
        ]

        dtype_str = str(series.dtype)
        is_date = _infer_is_date(series, col)
        is_id = _infer_is_id(series, col)

        col_min = col_max = col_mean = None
        if pd.api.types.is_numeric_dtype(series):
            col_min = _safe_stat(series.min())
            col_max = _safe_stat(series.max())
            col_mean = round(float(series.mean()), 4) if not series.isna().all() else None

        profile = ColumnProfile(
            name=col,
            dtype=dtype_str,
            null_count=null_count,
            null_pct=null_pct,
            unique_count=unique_count,
            sample_values=sample_values,
            is_date=is_date,
            is_id=is_id,
            min=col_min,
            max=col_max,
            mean=col_mean,
        )
        columns.append(profile)

        if is_date:
            date_columns.append(col)
        if is_id:
            potential_join_keys.append(col)

    return DatasetProfile(
        row_count=len(df),
        column_count=len(df.columns),
        columns=columns,
        date_columns=date_columns,
        potential_join_keys=potential_join_keys,
    )


def profile_bytes(data: bytes, filename: str) -> DatasetProfile:
    """Parse CSV or XLSX from bytes and return a DatasetProfile."""
    if filename.lower().endswith((".xlsx", ".xls")):
        df = pd.read_excel(io.BytesIO(data))
    else:
        df = pd.read_csv(io.BytesIO(data))
    return profile_dataframe(df)


def load_dataframe(data: bytes, filename: str) -> pd.DataFrame:
    """Load a CSV or XLSX file from bytes into a DataFrame."""
    if filename.lower().endswith((".xlsx", ".xls")):
        return pd.read_excel(io.BytesIO(data))
    return pd.read_csv(io.BytesIO(data))
