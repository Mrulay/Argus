"""LLM service — OpenAI client + prompt helpers."""
from __future__ import annotations

import json
import logging
from typing import Any

from openai import OpenAI

from app.config import get_settings
from app.models import (
    AdvisoryReport,
    ColumnProfile,
    DatasetProfile,
    Forecast,
    KPIProposal,
    RiskSignal,
    ComplianceNote,
    Recommendation,
    KPIFilter,
    KPIPlan,
)

logger = logging.getLogger(__name__)


def _client() -> OpenAI:
    return OpenAI(api_key=get_settings().openai_api_key)


def _chat(system: str, user: str, response_format: str = "json_object") -> Any:
    settings = get_settings()
    response = _client().chat.completions.create(
        model=settings.openai_model,
        response_format={"type": response_format},
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0.2,
    )
    content = response.choices[0].message.content
    if response_format == "json_object":
        return json.loads(content)
    return content


# ---------------------------------------------------------------------------
# Business model interpretation
# ---------------------------------------------------------------------------

def interpret_business_model(business_description: str, profile: DatasetProfile) -> str:
    schema_summary = _schema_summary(profile)
    system = (
        "You are an expert business analyst. "
        "Summarize the business model in 2-3 concise sentences based on "
        "the description and dataset schema provided."
    )
    user = (
        f"Business description: {business_description}\n\n"
        f"Dataset schema:\n{schema_summary}"
    )
    return _chat(system, user, response_format="text")


# ---------------------------------------------------------------------------
# KPI generation
# ---------------------------------------------------------------------------

def generate_kpi_proposals(
    business_description: str,
    profile: DatasetProfile,
    business_model_summary: str,
) -> list[KPIProposal]:
    schema_summary = _schema_summary(profile)
    system = """You are a senior data analyst. Propose 5-8 actionable KPIs for the business.
Return a JSON object with key "kpis" whose value is a list of KPI objects.
Each KPI object must have these fields:
  name (string), description (string), rationale (string), formula (string),
  target (number or null), unit (string or null),
  plan: {
    metric: one of [sum, mean, count, count_distinct, ratio, growth_rate],
    column: string or null,
    numerator_column: string or null,
    denominator_column: string or null,
    filters: [] (list of {column, operator, value}),
    group_by: [] (list of column names),
    time_column: string or null,
    time_window_days: integer or null
  }
Only reference columns that exist in the schema."""
    user = (
        f"Business description: {business_description}\n\n"
        f"Business model summary: {business_model_summary}\n\n"
        f"Dataset schema:\n{schema_summary}"
    )
    data = _chat(system, user)
    proposals = []
    for item in data.get("kpis", []):
        plan_data = item.get("plan", {})
        filters = [
            KPIFilter(**f) for f in plan_data.get("filters", [])
        ]
        plan = KPIPlan(
            metric=plan_data.get("metric", "count"),
            column=plan_data.get("column"),
            numerator_column=plan_data.get("numerator_column"),
            denominator_column=plan_data.get("denominator_column"),
            filters=filters,
            group_by=plan_data.get("group_by", []),
            time_column=plan_data.get("time_column"),
            time_window_days=plan_data.get("time_window_days"),
        )
        proposals.append(
            KPIProposal(
                name=item["name"],
                description=item["description"],
                rationale=item["rationale"],
                formula=item["formula"],
                plan=plan,
                target=item.get("target"),
                unit=item.get("unit"),
            )
        )
    return proposals


# ---------------------------------------------------------------------------
# Advisory report generation
# ---------------------------------------------------------------------------

def generate_advisory_report(
    business_description: str,
    business_model_summary: str,
    kpi_results: list[dict[str, Any]],
    profile: DatasetProfile,
) -> tuple[str, list[RiskSignal], list[ComplianceNote], list[Forecast], list[Recommendation]]:
    system = """You are a management consultant. Analyse the KPI results and produce a structured advisory report.
Return a JSON object with these keys:
  business_model_summary (string),
  risks: [{title, description, severity (low|medium|high)}],
  compliance_notes: [{regulation, observation, action_required (bool)}],
  forecasts: [{kpi_name, horizon_days (int), trend (up|down|flat), narrative}],
  recommendations: [{title, description, requires_approval (bool)}]"""
    kpi_text = "\n".join(
        f"- {r['name']}: {r['value']} {r.get('unit', '')} (target: {r.get('target', 'n/a')})"
        for r in kpi_results
    )
    schema_summary = _schema_summary(profile)
    user = (
        f"Business description: {business_description}\n\n"
        f"Business model summary: {business_model_summary}\n\n"
        f"KPI results:\n{kpi_text}\n\n"
        f"Dataset schema:\n{schema_summary}"
    )
    data = _chat(system, user)
    bm_summary = data.get("business_model_summary", business_model_summary)
    risks = [RiskSignal(**r) for r in data.get("risks", [])]
    compliance = [ComplianceNote(**c) for c in data.get("compliance_notes", [])]
    forecasts = [Forecast(**f) for f in data.get("forecasts", [])]
    recommendations = [Recommendation(**r) for r in data.get("recommendations", [])]
    return bm_summary, risks, compliance, forecasts, recommendations


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _schema_summary(profile: DatasetProfile) -> str:
    lines = [f"Rows: {profile.row_count}, Columns: {profile.column_count}"]
    for col in profile.columns:
        extras = []
        if col.is_date:
            extras.append("date")
        if col.is_id:
            extras.append("id")
        if col.null_pct > 0:
            extras.append(f"{col.null_pct}% null")
        tag = f" [{', '.join(extras)}]" if extras else ""
        lines.append(f"  {col.name} ({col.dtype}){tag} — sample: {col.sample_values[:3]}")
    return "\n".join(lines)
