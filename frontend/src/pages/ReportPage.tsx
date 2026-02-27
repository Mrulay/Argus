import { useEffect, useState } from 'react';
import { getLatestReport, approveRecommendations, type AdvisoryReport } from '../api/client';

const TREND_ICON = { up: '↑', down: '↓', flat: '→' } as const;

export default function ReportPage() {
  const projectId = localStorage.getItem('argus_project_id') ?? '';
  const [report, setReport] = useState<AdvisoryReport | null>(null);
  const [approvals, setApprovals] = useState<Record<number, boolean>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [polling, setPolling] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  useEffect(() => {
    if (!projectId) return;
    let interval: number | undefined;

    const fetchReport = () => {
      getLatestReport(projectId)
        .then(data => {
          setReport(data);
          const init: Record<number, boolean> = {};
          data.recommendations.forEach((r, i) => { if (r.approved != null) init[i] = r.approved; });
          setApprovals(init);
          setPolling(false);
          if (interval) window.clearInterval(interval);
        })
        .catch(err => {
          const message = String(err);
          setError(message);
          if (message.includes('No report') || message.includes('404')) {
            setPolling(true);
          }
        })
        .finally(() => setLoading(false));
    };

    fetchReport();
    interval = window.setInterval(fetchReport, 2000);

    return () => {
      if (interval) window.clearInterval(interval);
    };
  }, [projectId]);

  async function handleApproveRecommendations() {
    if (!report) return;
    setSaving(true);
    try {
      const updated = await approveRecommendations(projectId, report.report_id, approvals);
      setReport(updated);
      setSuccess('Recommendation approvals saved.');
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSaving(false);
    }
  }

  if (!projectId) return <div className="error-msg">No active project. Please upload data first.</div>;
  if (loading) {
    return (
      <div className="loading-state">
        <div className="loading-orbit" />
        <div className="loading-text">Loading advisory report…</div>
      </div>
    );
  }

  if (error && !report) {
    return (
      <div>
        <div className="page-header"><h1>Advisory Report</h1></div>
        {polling ? (
          <div className="loading-state">
            <div className="loading-orbit" />
            <div className="loading-text">Report is generating. Checking again…</div>
          </div>
        ) : (
          <div className="error-msg">{error}</div>
        )}
      </div>
    );
  }

  if (!report) return null;

  return (
    <div>
      <div className="page-header">
        <h1>Advisory Report</h1>
        <p>Generated {new Date(report.created_at).toLocaleString()}</p>
      </div>

      {/* Business Model Summary */}
      <div className="card">
        <h2 style={{ margin: '0 0 10px', fontSize: 18 }}>Business Model Summary</h2>
        <p style={{ margin: 0, lineHeight: 1.7 }}>{report.business_model_summary}</p>
      </div>

      {/* Risk Signals */}
      {report.risks.length > 0 && (
        <div className="card">
          <h2 style={{ margin: '0 0 14px', fontSize: 18 }}>Risk Signals</h2>
          {report.risks.map((r, i) => (
            <div key={i} style={{ marginBottom: 12, paddingBottom: 12, borderBottom: i < report.risks.length - 1 ? '1px solid #f3f4f6' : 'none' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                <span className={`badge badge-${r.severity}`}>{r.severity}</span>
                <strong>{r.title}</strong>
              </div>
              <p style={{ margin: 0, color: '#6b7280', fontSize: 14 }}>{r.description}</p>
            </div>
          ))}
        </div>
      )}

      {/* Compliance Notes */}
      {report.compliance_notes.length > 0 && (
        <div className="card">
          <h2 style={{ margin: '0 0 14px', fontSize: 18 }}>Compliance Notes</h2>
          <table>
            <thead>
              <tr>
                <th>Regulation</th>
                <th>Observation</th>
                <th>Action Required</th>
              </tr>
            </thead>
            <tbody>
              {report.compliance_notes.map((c, i) => (
                <tr key={i}>
                  <td><strong>{c.regulation}</strong></td>
                  <td style={{ color: '#6b7280' }}>{c.observation}</td>
                  <td>
                    {c.action_required
                      ? <span className="badge badge-high">Yes</span>
                      : <span className="badge badge-approved">No</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Forecasts */}
      {report.forecasts.length > 0 && (
        <div className="card">
          <h2 style={{ margin: '0 0 14px', fontSize: 18 }}>Forecasts</h2>
          {report.forecasts.map((f, i) => (
            <div key={i} style={{ marginBottom: 12, paddingBottom: 12, borderBottom: i < report.forecasts.length - 1 ? '1px solid #f3f4f6' : 'none' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                <strong>{f.kpi_name}</strong>
                <span style={{ fontSize: 18 }}>{TREND_ICON[f.trend]}</span>
                <span style={{ fontSize: 13, color: '#6b7280' }}>{f.horizon_days}-day horizon</span>
              </div>
              <p style={{ margin: 0, color: '#6b7280', fontSize: 14 }}>{f.narrative}</p>
            </div>
          ))}
        </div>
      )}

      {/* Recommendations (human approval gate) */}
      {report.recommendations.length > 0 && (
        <div className="card">
          <h2 style={{ margin: '0 0 6px', fontSize: 18 }}>Recommendations</h2>
          <p style={{ margin: '0 0 16px', fontSize: 14, color: '#6b7280' }}>
            Recommendations that affect pricing, compliance, or operations require your explicit approval.
          </p>

          {error && <div className="error-msg" style={{ marginBottom: 12 }}>{error}</div>}
          {success && <div className="info-msg" style={{ marginBottom: 12 }}>{success}</div>}

          {report.recommendations.map((rec, i) => (
            <div
              key={i}
              style={{
                marginBottom: 16,
                paddingBottom: 16,
                borderBottom: i < report.recommendations.length - 1 ? '1px solid #f3f4f6' : 'none',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                <div style={{ flex: 1 }}>
                  <strong style={{ display: 'block', marginBottom: 4 }}>{rec.title}</strong>
                  <p style={{ margin: 0, color: '#6b7280', fontSize: 14 }}>{rec.description}</p>
                  {rec.approved != null && (
                    <span className={`badge badge-${rec.approved ? 'approved' : 'rejected'}`} style={{ marginTop: 6 }}>
                      {rec.approved ? 'Approved' : 'Rejected'}
                    </span>
                  )}
                </div>

                {rec.requires_approval && (
                  <div style={{ display: 'flex', gap: 8, marginLeft: 16, flexShrink: 0 }}>
                    <button
                      className={approvals[i] === true ? 'btn-success' : 'btn-ghost'}
                      onClick={() => setApprovals(p => ({ ...p, [i]: true }))}
                    >
                      ✓ Approve
                    </button>
                    <button
                      className={approvals[i] === false ? 'btn-danger' : 'btn-ghost'}
                      onClick={() => setApprovals(p => ({ ...p, [i]: false }))}
                    >
                      ✗ Reject
                    </button>
                  </div>
                )}
              </div>
            </div>
          ))}

          {report.recommendations.some(r => r.requires_approval) && (
            <button className="btn-primary" onClick={handleApproveRecommendations} disabled={saving}>
              {saving ? 'Saving…' : 'Save Recommendation Approvals'}
            </button>
          )}
        </div>
      )}
    </div>
  );
}
