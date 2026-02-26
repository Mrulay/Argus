"""Tests for the data profiler service."""
from __future__ import annotations

import io

import pandas as pd
import pytest

from app.models import DatasetProfile
from app.services.profiler import profile_dataframe, profile_bytes


def _make_df() -> pd.DataFrame:
    return pd.DataFrame({
        "order_id": ["A001", "A002", "A003", "A004", "A005"],
        "created_at": pd.to_datetime([
            "2024-01-01", "2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05"
        ]),
        "revenue": [100.0, 200.0, None, 150.0, 300.0],
        "customer_id": [1, 2, 3, 4, 5],
        "category": ["A", "B", "A", "C", None],
    })


class TestProfileDataframe:
    def test_row_and_column_count(self):
        df = _make_df()
        profile = profile_dataframe(df)
        assert profile.row_count == 5
        assert profile.column_count == 5

    def test_date_column_detection(self):
        df = _make_df()
        profile = profile_dataframe(df)
        assert "created_at" in profile.date_columns

    def test_id_column_detection(self):
        df = _make_df()
        profile = profile_dataframe(df)
        # order_id and customer_id should be detected as potential join keys
        join_keys = profile.potential_join_keys
        assert any("id" in k.lower() for k in join_keys)

    def test_null_count_and_pct(self):
        df = _make_df()
        profile = profile_dataframe(df)
        revenue_col = next(c for c in profile.columns if c.name == "revenue")
        assert revenue_col.null_count == 1
        assert revenue_col.null_pct == 20.0

    def test_numeric_stats(self):
        df = _make_df()
        profile = profile_dataframe(df)
        revenue_col = next(c for c in profile.columns if c.name == "revenue")
        assert revenue_col.mean is not None
        assert abs(revenue_col.mean - 187.5) < 0.01

    def test_sample_values_present(self):
        df = _make_df()
        profile = profile_dataframe(df)
        order_col = next(c for c in profile.columns if c.name == "order_id")
        assert len(order_col.sample_values) > 0

    def test_returns_dataset_profile_type(self):
        df = _make_df()
        profile = profile_dataframe(df)
        assert isinstance(profile, DatasetProfile)


class TestProfileBytes:
    def test_csv_bytes(self):
        df = _make_df()
        buf = io.StringIO()
        df.to_csv(buf, index=False)
        csv_bytes = buf.getvalue().encode()
        profile = profile_bytes(csv_bytes, "test.csv")
        assert profile.row_count == 5
        assert profile.column_count == 5

    def test_empty_dataframe(self):
        df = pd.DataFrame({"a": [], "b": []})
        profile = profile_dataframe(df)
        assert profile.row_count == 0
        assert profile.column_count == 2

    def test_all_null_column(self):
        df = pd.DataFrame({"a": [None, None, None], "b": [1, 2, 3]})
        profile = profile_dataframe(df)
        a_col = next(c for c in profile.columns if c.name == "a")
        assert a_col.null_count == 3
        assert a_col.null_pct == 100.0
