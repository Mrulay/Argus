/**
 * Argus API client — typed wrappers around the FastAPI backend.
 */

const BASE = import.meta.env.VITE_API_URL ?? '/api';

async function request<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...options.headers },
    ...options,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`${res.status} ${res.statusText}: ${text}`);
  }
  return res.json() as Promise<T>;
}

// ── Types ────────────────────────────────────────────────────────────────────

export interface Project {
  project_id: string;
  name: string;
  business_description: string;
  created_at: string;
  status: string;
}

export interface Dataset {
  dataset_id: string;
  project_id: string;
  filename: string;
  s3_key: string;
  profile?: DatasetProfile;
  created_at: string;
}

export interface ColumnProfile {
  name: string;
  dtype: string;
  null_count: number;
  null_pct: number;
  unique_count: number;
  sample_values: unknown[];
  is_date: boolean;
  is_id: boolean;
  min?: number | null;
  max?: number | null;
  mean?: number | null;
}

export interface DatasetProfile {
  row_count: number;
  column_count: number;
  columns: ColumnProfile[];
  potential_join_keys: string[];
  date_columns: string[];
}

export type KPIStatus = 'proposed' | 'approved' | 'rejected';

export interface KPIPlan {
  metric: string;
  column?: string | null;
  numerator_column?: string | null;
  denominator_column?: string | null;
  filters: { column: string; operator: string; value: unknown }[];
  group_by: string[];
  time_column?: string | null;
  time_window_days?: number | null;
}

export interface KPI {
  kpi_id: string;
  project_id: string;
  name: string;
  description: string;
  rationale: string;
  formula: string;
  plan: KPIPlan;
  target?: number | null;
  unit?: string | null;
  status: KPIStatus;
  value?: number | null;
  value_label?: string | null;
  value_breakdown?: { label: string; value: number; pct?: number | null }[] | null;
  computed_at?: string | null;
  created_at: string;
}

export type JobStatus =
  | 'queued'
  | 'running'
  | 'awaiting_kpi_approval'
  | 'awaiting_recommendation_approval'
  | 'complete'
  | 'failed';

export type JobStage = 'profile' | 'generate_kpis' | 'compute_kpis' | 'generate_report';

export interface Job {
  job_id: string;
  project_id: string;
  stage: JobStage;
  status: JobStatus;
  error?: string | null;
  created_at: string;
  updated_at: string;
}

export interface RiskSignal {
  title: string;
  description: string;
  severity: 'low' | 'medium' | 'high';
}

export interface ComplianceNote {
  regulation: string;
  observation: string;
  action_required: boolean;
}

export interface Forecast {
  kpi_name: string;
  horizon_days: number;
  trend: 'up' | 'down' | 'flat';
  narrative: string;
}

export interface Recommendation {
  title: string;
  description: string;
  requires_approval: boolean;
  approved?: boolean | null;
}

export interface AdvisoryReport {
  report_id: string;
  project_id: string;
  business_model_summary: string;
  risks: RiskSignal[];
  compliance_notes: ComplianceNote[];
  forecasts: Forecast[];
  recommendations: Recommendation[];
  created_at: string;
  s3_key: string;
}

export type DashboardWidgetType = 'kpi_card' | 'bar' | 'line' | 'area' | 'pie' | 'table';

export interface DashboardWidget {
  widget_id: string;
  type: DashboardWidgetType;
  title: string;
  description?: string | null;
  kpi_ids: string[];
  size?: 'sm' | 'md' | 'lg' | 'xl';
  section?: string | null;
  value_key?: 'value' | 'pct' | null;
}

export interface DashboardSpec {
  dashboard_id: string;
  project_id: string;
  title: string;
  summary?: string | null;
  widgets: DashboardWidget[];
  created_at: string;
}

// ── Projects ─────────────────────────────────────────────────────────────────

export const createProject = (body: { name: string; business_description: string }) =>
  request<Project>('/projects/', { method: 'POST', body: JSON.stringify(body) });

export const getProject = (projectId: string) =>
  request<Project>(`/projects/${projectId}`);

export const listProjects = () =>
  request<Project[]>('/projects/');

// ── Datasets ─────────────────────────────────────────────────────────────────

export const uploadDataset = async (projectId: string, file: File): Promise<Dataset> => {
  const form = new FormData();
  form.append('file', file);
  const res = await fetch(`${BASE}/projects/${projectId}/datasets/`, {
    method: 'POST',
    body: form,
  });
  if (!res.ok) throw new Error(`Upload failed: ${res.statusText}`);
  return res.json();
};

export const uploadDatasets = async (projectId: string, files: File[]): Promise<Dataset[]> => {
  const form = new FormData();
  files.forEach(file => form.append('files', file));
  const res = await fetch(`${BASE}/projects/${projectId}/datasets/batch`, {
    method: 'POST',
    body: form,
  });
  if (!res.ok) throw new Error(`Upload failed: ${res.statusText}`);
  return res.json();
};

export const getDataset = (projectId: string, datasetId: string) =>
  request<Dataset>(`/projects/${projectId}/datasets/${datasetId}`);

export const getProfile = (projectId: string, datasetId: string) =>
  request<DatasetProfile>(`/projects/${projectId}/datasets/${datasetId}/profile`);

// ── KPIs ─────────────────────────────────────────────────────────────────────

export const listKPIs = (projectId: string) =>
  request<KPI[]>(`/projects/${projectId}/kpis/`);

export const approveKPIs = (projectId: string, approvals: Record<string, KPIStatus>) =>
  request<KPI[]>(`/projects/${projectId}/kpis/approve`, {
    method: 'POST',
    body: JSON.stringify({ approvals }),
  });

// ── Jobs ─────────────────────────────────────────────────────────────────────

export const createJob = (projectId: string, stage: JobStage, datasetId?: string) => {
  const params = new URLSearchParams({ stage });
  if (datasetId) params.append('dataset_id', datasetId);
  return request<Job>(`/projects/${projectId}/jobs/?${params}`, { method: 'POST' });
};

export const getJob = (projectId: string, jobId: string) =>
  request<Job>(`/projects/${projectId}/jobs/${jobId}`);

export const listJobs = (projectId: string) =>
  request<Job[]>(`/projects/${projectId}/jobs/`);

// ── Dashboard ───────────────────────────────────────────────────────────────

export const getLatestDashboard = (projectId: string) =>
  request<DashboardSpec>(`/projects/${projectId}/dashboard/latest`);

// ── Reports ──────────────────────────────────────────────────────────────────

export const getLatestReport = (projectId: string) =>
  request<AdvisoryReport>(`/projects/${projectId}/reports/latest`);

export const approveRecommendations = (
  projectId: string,
  reportId: string,
  approvals: Record<number, boolean>
) =>
  request<AdvisoryReport>(
    `/projects/${projectId}/reports/${reportId}/approve-recommendations`,
    { method: 'POST', body: JSON.stringify({ approvals }) }
  );
