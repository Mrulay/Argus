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
    KPI,
    KPIProposal,
    RiskSignal,
    ComplianceNote,
    Recommendation,
    KPIFilter,
    KPIPlan,
    DashboardSpec,
    DashboardWidget,
    DashboardWidgetType,
)

logger = logging.getLogger(__name__)

_ALLOWED_OPERATORS = {"eq", "ne", "gt", "lt", "gte", "lte", "in"}
_ALLOWED_WIDGETS = {w.value for w in DashboardWidgetType}
_ALLOWED_METRICS = {"sum", "mean", "count", "count_distinct", "ratio", "growth_rate", "mean_days_between"}


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
Filters must use ONLY these operators: [eq, ne, gt, lt, gte, lte, in].
Never use aggregation words (e.g., COUNT, SUM) as filter operators.
If you include a ratio metric, you MUST supply both numerator_column and denominator_column.
For mix/segment KPIs (e.g., sales mix by category), include a group_by column so the breakdown can be stored.
Only reference columns that exist in the schema."""
    user = (
        f"Business description: {business_description}\n\n"
        f"Business model summary: {business_model_summary}\n\n"
        f"Dataset schema:\n{schema_summary}"
    )
    attempts = 2
    last_invalid = 0
    for attempt in range(1, attempts + 1):
        data = _chat(system, user)
        proposals: list[KPIProposal] = []
        invalid_count = 0
        for item in data.get("kpis", []):
            plan_data = item.get("plan", {})
            filters = [
                KPIFilter(**f) for f in plan_data.get("filters", [])
            ]
            invalid_ops = [f.operator for f in filters if f.operator not in _ALLOWED_OPERATORS]
            metric = plan_data.get("metric", "count")
            num_col = plan_data.get("numerator_column")
            den_col = plan_data.get("denominator_column")
            invalid_ratio = metric == "ratio" and (not num_col or not den_col)
            if invalid_ops or invalid_ratio:
                invalid_count += 1
                logger.warning(
                    "Invalid KPI plan discarded name=%s invalid_ops=%s invalid_ratio=%s",
                    item.get("name"),
                    invalid_ops,
                    invalid_ratio,
                )
                continue
            plan = KPIPlan(
                metric=metric,
                column=plan_data.get("column"),
                numerator_column=num_col,
                denominator_column=den_col,
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

        if invalid_count == 0 or attempt == attempts:
            return proposals

        last_invalid = invalid_count
        logger.warning("Retrying KPI proposal generation invalid_count=%s attempt=%s", invalid_count, attempt)

    logger.warning("KPI proposal retries exhausted invalid_count=%s", last_invalid)
    return []


def generate_custom_kpi(
    user_request: str,
    business_description: str,
    profile: DatasetProfile,
) -> tuple[bool, str, KPIProposal | None]:
    schema_summary = _schema_summary(profile)
    system = """You are a senior data analyst. Validate and propose a single KPI based on the user request.
Return a JSON object with keys:
  viable (bool), reason (string), kpi (object or null)
If viable is true, kpi must have:
  name, description, rationale, formula, target (number or null), unit (string or null),
  plan: {
    metric: one of [sum, mean, count, count_distinct, ratio, growth_rate, mean_days_between],
    column, numerator_column, denominator_column, filters, group_by, time_column, time_window_days
  }
Filters must use ONLY these operators: [eq, ne, gt, lt, gte, lte, in].
If metric is ratio, numerator_column and denominator_column are required.
Only reference columns that exist in the schema."""
    user = (
        f"Business description: {business_description}\n\n"
        f"User request: {user_request}\n\n"
        f"Dataset schema:\n{schema_summary}"
    )
    data = _chat(system, user)
    viable = bool(data.get("viable", False))
    reason = str(data.get("reason", ""))
    kpi_data = data.get("kpi") or None
    if not viable or not kpi_data:
        return False, reason or "Request not viable", None

    plan_data = kpi_data.get("plan", {})
    metric = plan_data.get("metric", "count")
    if metric not in _ALLOWED_METRICS:
        return False, "Unsupported metric", None

    filters = [KPIFilter(**f) for f in plan_data.get("filters", [])]
    invalid_ops = [f.operator for f in filters if f.operator not in _ALLOWED_OPERATORS]
    if invalid_ops:
        return False, f"Invalid operators: {invalid_ops}", None

    num_col = plan_data.get("numerator_column")
    den_col = plan_data.get("denominator_column")
    if metric == "ratio" and (not num_col or not den_col):
        return False, "Ratio metric requires numerator and denominator", None

    plan = KPIPlan(
        metric=metric,
        column=plan_data.get("column"),
        numerator_column=num_col,
        denominator_column=den_col,
        filters=filters,
        group_by=plan_data.get("group_by", []),
        time_column=plan_data.get("time_column"),
        time_window_days=plan_data.get("time_window_days"),
    )
    proposal = KPIProposal(
        name=kpi_data["name"],
        description=kpi_data["description"],
        rationale=kpi_data["rationale"],
        formula=kpi_data["formula"],
        plan=plan,
        target=kpi_data.get("target"),
        unit=kpi_data.get("unit"),
    )
    return True, reason or "", proposal


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
Focus on business shortcomings, market/operational risks, and forward-looking forecasts.
Do not mention or speculate about KPI calculation quality or data processing deficiencies.
Return a JSON object with these keys:
  business_model_summary (string),
  risks: [{title, description, severity (low|medium|high)}],
  compliance_notes: [{regulation, observation, action_required (bool)}],
  forecasts: [{kpi_name, horizon_days (int), trend (up|down|flat), narrative}],
    recommendations: [{title, description, requires_approval (bool)}].
Recommendations must address business shortcomings, operational improvements, or growth opportunities.
Avoid diagnosing KPI formulas, data quality, or computation issues."""
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
# Dashboard spec generation
# ---------------------------------------------------------------------------

def generate_dashboard_spec(
    project_id: str,
    business_description: str,
    profile: DatasetProfile,
    kpis: list[KPI],
) -> DashboardSpec | None:
    kpi_summary = "\n".join(
        f"- {k.kpi_id}: {k.name} = {k.value} {k.unit or ''}" for k in kpis
    )
    schema_summary = _schema_summary(profile)
    system = """You are a data visualization designer.
Return a JSON object with key "dashboard" containing:
  title (string), summary (string or null), widgets (list)
Each widget:
  type: one of [kpi_card, bar, line, area, pie, table]
  title: string
  description: string or null
    size: one of [sm, md, lg, xl]
    section: string or null (used to group widgets into sections)
    value_key: "value" or "pct" (optional; choose how to plot breakdowns)
  kpi_ids: list of KPI IDs to visualize
Use only KPI IDs provided. Do not invent IDs."""
    user = (
        f"Business description: {business_description}\n\n"
        f"KPI list (id: name = value unit):\n{kpi_summary}\n\n"
        f"Dataset schema:\n{schema_summary}"
    )
    data = _chat(system, user)
    dashboard = data.get("dashboard", {})
    widgets_data = dashboard.get("widgets", [])

    valid_kpi_ids = {k.kpi_id for k in kpis}
    widgets: list[DashboardWidget] = []
    for item in widgets_data:
        widget_type = item.get("type")
        size = item.get("size", "md")
        section = item.get("section")
        value_key = item.get("value_key")
        kpi_ids = [k for k in item.get("kpi_ids", []) if k in valid_kpi_ids]
        if size not in {"sm", "md", "lg", "xl"}:
            size = "md"
        if widget_type not in _ALLOWED_WIDGETS or not kpi_ids:
            logger.warning("Dashboard widget discarded type=%s kpi_ids=%s", widget_type, kpi_ids)
            continue
        if value_key not in {None, "value", "pct"}:
            value_key = None

        widgets.append(
            DashboardWidget(
                type=DashboardWidgetType(widget_type),
                title=item.get("title", "Untitled"),
                description=item.get("description"),
                kpi_ids=kpi_ids,
                size=size,
                section=section,
                value_key=value_key,
            )
        )

    if not widgets:
        logger.warning("Dashboard spec invalid: no widgets")
        return None

    return DashboardSpec(
        project_id=project_id,
        title=dashboard.get("title", "KPI Dashboard"),
        summary=dashboard.get("summary"),
        widgets=widgets,
    )


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
