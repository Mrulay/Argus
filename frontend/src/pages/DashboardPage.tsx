import { useEffect, useState } from 'react';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from 'recharts';
import { listKPIs, listJobs, type KPI, type Job } from '../api/client';

function KPICard({ kpi }: { kpi: KPI }) {
  const hasValue = kpi.value != null;
  const pct = kpi.target && kpi.value != null
    ? Math.min(100, Math.round((kpi.value / kpi.target) * 100))
    : null;

  return (
    <div className="card" style={{ flex: '1 1 220px', minWidth: 220 }}>
      <div style={{ fontSize: 13, color: '#6b7280', marginBottom: 4 }}>{kpi.name}</div>
      <div style={{ fontSize: 28, fontWeight: 700, color: '#1a202c' }}>
        {hasValue
          ? `${Number(kpi.value!.toFixed(2)).toLocaleString()}${kpi.unit ? ` ${kpi.unit}` : ''}`
          : '—'}
      </div>
      {pct != null && (
        <div style={{ marginTop: 8 }}>
          <div style={{ fontSize: 12, color: '#6b7280', marginBottom: 4 }}>
            {pct}% of target {kpi.target?.toLocaleString()} {kpi.unit}
          </div>
          <div style={{ height: 6, background: '#e5e7eb', borderRadius: 9999 }}>
            <div
              style={{
                width: `${pct}%`,
                height: '100%',
                background: pct >= 100 ? '#10b981' : pct >= 60 ? '#f59e0b' : '#ef4444',
                borderRadius: 9999,
                transition: 'width 0.6s',
              }}
            />
          </div>
        </div>
      )}
      {kpi.computed_at && (
        <div style={{ fontSize: 11, color: '#9ca3af', marginTop: 8 }}>
          Computed {new Date(kpi.computed_at).toLocaleString()}
        </div>
      )}
    </div>
  );
}

export default function DashboardPage() {
  const projectId = localStorage.getItem('argus_project_id') ?? '';
  const [kpis, setKpis] = useState<KPI[]>([]);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!projectId) return;
    Promise.all([listKPIs(projectId), listJobs(projectId)])
      .then(([k, j]) => { setKpis(k); setJobs(j); })
      .catch(err => setError(String(err)))
      .finally(() => setLoading(false));
  }, [projectId]);

  if (!projectId) return <div className="error-msg">No active project. Please upload data first.</div>;
  if (loading) return <div className="spinner">Loading dashboard…</div>;

  const approved = kpis.filter(k => k.status === 'approved');
  const computed = approved.filter(k => k.value != null);
  const chartData = computed.map(k => ({
    name: k.name.length > 20 ? k.name.slice(0, 18) + '…' : k.name,
    value: Number((k.value ?? 0).toFixed(2)),
    target: k.target ?? undefined,
  }));

  const latestJob = jobs.sort((a, b) => b.updated_at.localeCompare(a.updated_at))[0];

  return (
    <div>
      <div className="page-header">
        <h1>KPI Dashboard</h1>
        <p>Computed values for approved KPIs.</p>
      </div>

      {error && <div className="error-msg" style={{ marginBottom: 16 }}>{error}</div>}

      {latestJob && (
        <div className="card" style={{ padding: '14px 20px' }}>
          <span style={{ fontSize: 13, color: '#6b7280' }}>Latest job: </span>
          <strong style={{ fontSize: 13 }}>{latestJob.stage}</strong>
          <span style={{ marginLeft: 10 }}>
            <span className={`badge badge-${latestJob.status}`}>{latestJob.status}</span>
          </span>
          {latestJob.error && (
            <span style={{ marginLeft: 10, fontSize: 12, color: '#ef4444' }}>{latestJob.error}</span>
          )}
        </div>
      )}

      {approved.length === 0 ? (
        <div className="info-msg">No approved KPIs yet. Please complete the approval step.</div>
      ) : (
        <>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 16, marginBottom: 24 }}>
            {approved.map(kpi => <KPICard key={kpi.kpi_id} kpi={kpi} />)}
          </div>

          {chartData.length > 0 && (
            <div className="card">
              <h2 style={{ margin: '0 0 16px', fontSize: 18 }}>KPI Values</h2>
              <ResponsiveContainer width="100%" height={280}>
                <BarChart data={chartData} margin={{ top: 0, right: 16, left: 0, bottom: 40 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" />
                  <XAxis dataKey="name" tick={{ fontSize: 12 }} angle={-20} textAnchor="end" />
                  <YAxis tick={{ fontSize: 12 }} />
                  <Tooltip />
                  <Bar dataKey="value" fill="#4f46e5" radius={[4, 4, 0, 0]} />
                  {chartData.some(d => d.target != null) && (
                    <Bar dataKey="target" fill="#d1d5db" radius={[4, 4, 0, 0]} />
                  )}
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </>
      )}
    </div>
  );
}
