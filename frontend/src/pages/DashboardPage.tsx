import { useEffect, useState } from 'react';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  LineChart, Line, AreaChart, Area, PieChart, Pie, Cell,
} from 'recharts';
import {
  listKPIs,
  listJobs,
  getLatestDashboard,
  type KPI,
  type Job,
  type DashboardSpec,
  type DashboardWidget,
} from '../api/client';

const PIE_COLORS = ['#0f766e', '#0ea5e9', '#f97316', '#8b5cf6', '#22c55e', '#f43f5e'];

function KPICard({ kpi, compact = false }: { kpi: KPI; compact?: boolean }) {
  const hasValue = kpi.value != null;
  const pct = kpi.target && kpi.value != null
    ? Math.min(100, Math.round((kpi.value / kpi.target) * 100))
    : null;

  return (
    <div className={compact ? '' : 'card'} style={{ flex: '1 1 220px', minWidth: 220 }}>
      <div style={{ fontSize: 13, color: '#6b7280', marginBottom: 4 }}>{kpi.name}</div>
      <div style={{ fontSize: 28, fontWeight: 700, color: '#1a202c' }}>
        {hasValue
          ? `${Number(kpi.value!.toFixed(2)).toLocaleString()}${kpi.unit ? ` ${kpi.unit}` : ''}`
          : '—'}
      </div>
        {kpi.value_label && (
          <div style={{ fontSize: 12, color: '#6b7280', marginTop: 6 }}>
            Top group: {kpi.value_label}
          </div>
        )}
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
  const [dashboard, setDashboard] = useState<DashboardSpec | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!projectId) return;
    Promise.all([listKPIs(projectId), listJobs(projectId), getLatestDashboard(projectId)])
      .then(([k, j, d]) => { setKpis(k); setJobs(j); setDashboard(d); })
      .catch(err => {
        if (String(err).includes('dashboard')) {
          setDashboard(null);
        } else {
          setError(String(err));
        }
      })
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

  function buildWidgetData(widget: DashboardWidget) {
    const items = widget.kpi_ids
      .map(id => kpis.find(k => k.kpi_id === id))
      .filter((k): k is KPI => Boolean(k));
    if (items.length === 1 && items[0].value_breakdown && items[0].value_breakdown.length > 0) {
      return items[0].value_breakdown.map(entry => ({
        name: entry.label,
        value: Number(entry.value.toFixed(2)),
        pct: entry.pct != null ? Number(entry.pct.toFixed(2)) : undefined,
      }));
    }
    return items.map(k => ({
      name: k.name,
      value: Number((k.value ?? 0).toFixed(2)),
      unit: k.unit,
      target: k.target ?? undefined,
    }));
  }

  function resolveValueKey(widget: DashboardWidget, data: Array<{ pct?: number }>) {
    if (widget.value_key === 'value' || widget.value_key === 'pct') return widget.value_key;
    return data.every(row => row.pct != null) ? 'pct' : 'value';
  }

  function renderWidget(widget: DashboardWidget) {
    const data = buildWidgetData(widget);
    if (data.length === 0) return null;
    const size = widget.size ?? 'md';
    const sizeClass = `widget-card widget-${size}`;
    const chartClass = loading ? 'chart-loading' : '';

    if (widget.type === 'kpi_card') {
      const kpi = kpis.find(k => k.kpi_id === widget.kpi_ids[0]);
      if (!kpi) return null;
      return (
        <div className={`card ${sizeClass}`} key={widget.widget_id}>
          <KPICard kpi={kpi} compact />
        </div>
      );
    }

    if (widget.type === 'table') {
      const hasPct = data.some(row => row.pct != null);
      return (
        <div className={`card ${sizeClass}`} key={widget.widget_id}>
          <h3>{widget.title}</h3>
          <table className="kpi-table">
            <thead>
              <tr>
                <th>KPI</th>
                <th>Value</th>
                {hasPct && <th>%</th>}
              </tr>
            </thead>
            <tbody>
              {data.map((row, idx) => (
                <tr key={idx}>
                  <td>{row.name}</td>
                  <td>{row.value.toLocaleString()} {row.unit}</td>
                  {hasPct && <td>{row.pct != null ? `${row.pct}%` : '—'}</td>}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      );
    }

    if (widget.type === 'pie') {
      const valueKey = resolveValueKey(widget, data);
      return (
        <div className={`card ${sizeClass} ${chartClass}`} key={widget.widget_id}>
          <h3>{widget.title}</h3>
          <ResponsiveContainer width="100%" height={260}>
            <PieChart>
              <Pie data={data} dataKey={valueKey} nameKey="name" outerRadius={100} innerRadius={52}>
                {data.map((_, i) => (
                  <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                ))}
              </Pie>
              <Tooltip />
            </PieChart>
          </ResponsiveContainer>
        </div>
      );
    }

    if (widget.type === 'line') {
      const valueKey = resolveValueKey(widget, data);
      return (
        <div className={`card ${sizeClass} ${chartClass}`} key={widget.widget_id}>
          <h3>{widget.title}</h3>
          <ResponsiveContainer width="100%" height={260}>
            <LineChart data={data}>
              <CartesianGrid strokeDasharray="6 6" stroke="#e2e8f0" />
              <XAxis dataKey="name" tick={{ fontSize: 12 }} />
              <YAxis tick={{ fontSize: 12 }} />
              <Tooltip />
              <Line type="monotone" dataKey={valueKey} stroke="#0f766e" strokeWidth={3} dot={{ r: 4 }} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      );
    }

    if (widget.type === 'area') {
      const valueKey = resolveValueKey(widget, data);
      return (
        <div className={`card ${sizeClass} ${chartClass}`} key={widget.widget_id}>
          <h3>{widget.title}</h3>
          <ResponsiveContainer width="100%" height={260}>
            <AreaChart data={data}>
              <defs>
                <linearGradient id={`area-${widget.widget_id}`} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#0f766e" stopOpacity={0.7} />
                  <stop offset="95%" stopColor="#0f766e" stopOpacity={0.05} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="6 6" stroke="#e2e8f0" />
              <XAxis dataKey="name" tick={{ fontSize: 12 }} />
              <YAxis tick={{ fontSize: 12 }} />
              <Tooltip />
              <Area type="monotone" dataKey={valueKey} stroke="#0f766e" fill={`url(#area-${widget.widget_id})`} />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      );
    }

    const valueKey = resolveValueKey(widget, data);
    return (
      <div className={`card ${sizeClass} ${chartClass}`} key={widget.widget_id}>
        <h3>{widget.title}</h3>
        <ResponsiveContainer width="100%" height={260}>
          <BarChart data={data}>
            <CartesianGrid strokeDasharray="6 6" stroke="#e2e8f0" />
            <XAxis dataKey="name" tick={{ fontSize: 12 }} angle={-10} textAnchor="end" />
            <YAxis tick={{ fontSize: 12 }} />
            <Tooltip />
            <Bar dataKey={valueKey} fill="#0f766e" radius={[10, 10, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    );
  }

  const hasCustomDashboard = dashboard && dashboard.widgets.length > 0;
  const groupedWidgets = hasCustomDashboard
    ? dashboard!.widgets.reduce<Record<string, DashboardWidget[]>>((acc, widget) => {
        const key = widget.section ?? 'Overview';
        if (!acc[key]) acc[key] = [];
        acc[key].push(widget);
        return acc;
      }, {})
    : {};

  return (
    <div>
      <div className="page-header">
        <h1>{dashboard?.title ?? 'KPI Dashboard'}</h1>
        <p>{dashboard?.summary ?? 'Computed values for approved KPIs.'}</p>
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
        hasCustomDashboard ? (
          <div className="dashboard-sections">
            {Object.entries(groupedWidgets).map(([section, widgets]) => (
              <section key={section} className="dashboard-section">
                <div className="section-header">
                  <h2>{section}</h2>
                  <div className="section-rule" />
                </div>
                <div className="dashboard-grid">
                  {widgets.map(widget => renderWidget(widget))}
                </div>
              </section>
            ))}
          </div>
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
        )
      )}
    </div>
  );
}
