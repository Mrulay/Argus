import { useEffect, useState } from 'react';
import { listKPIs, approveKPIs, type KPI, type KPIStatus } from '../api/client';

export default function KPIApprovalPage() {
  const projectId = localStorage.getItem('argus_project_id') ?? '';
  const [kpis, setKpis] = useState<KPI[]>([]);
  const [approvals, setApprovals] = useState<Record<string, KPIStatus>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  useEffect(() => {
    if (!projectId) return;
    listKPIs(projectId)
      .then(data => {
        setKpis(data);
        const initial: Record<string, KPIStatus> = {};
        data.forEach(k => { initial[k.kpi_id] = k.status; });
        setApprovals(initial);
      })
      .catch(err => setError(String(err)))
      .finally(() => setLoading(false));
  }, [projectId]);

  async function handleSubmit() {
    setSaving(true);
    setError('');
    setSuccess('');
    try {
      const updated = await approveKPIs(projectId, approvals);
      setKpis(updated);
      const approvedCount = updated.filter(k => k.status === 'approved').length;
      setSuccess(`Saved! ${approvedCount} KPI(s) approved. KPI computation has been enqueued.`);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSaving(false);
    }
  }

  function setStatus(kpiId: string, status: KPIStatus) {
    setApprovals(prev => ({ ...prev, [kpiId]: status }));
  }

  if (!projectId) return <div className="error-msg">No active project. Please upload data first.</div>;
  if (loading) return <div className="spinner">Loading KPI proposals…</div>;

  return (
    <div>
      <div className="page-header">
        <h1>KPI Approval</h1>
        <p>
          Review the AI-proposed KPIs below. Approve the ones that align with your business goals.
          <strong> This approval is required before computation begins.</strong>
        </p>
      </div>

      {error && <div className="error-msg" style={{ marginBottom: 16 }}>{error}</div>}
      {success && <div className="info-msg" style={{ marginBottom: 16 }}>{success}</div>}

      {kpis.length === 0 ? (
        <div className="info-msg">
          No KPI proposals yet. Please wait for the profiling job to complete.
        </div>
      ) : (
        <>
          {kpis.map(kpi => (
            <div className="card" key={kpi.kpi_id}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                <div style={{ flex: 1 }}>
                  <h3 style={{ margin: '0 0 6px', fontSize: 16 }}>{kpi.name}</h3>
                  <p style={{ margin: '0 0 8px', color: '#6b7280', fontSize: 14 }}>{kpi.description}</p>
                  <div style={{ fontSize: 13, color: '#374151' }}>
                    <strong>Formula:</strong> <code>{kpi.formula}</code>
                  </div>
                  <div style={{ fontSize: 13, color: '#6b7280', marginTop: 4 }}>
                    <strong>Rationale:</strong> {kpi.rationale}
                  </div>
                  {kpi.target != null && (
                    <div style={{ fontSize: 13, color: '#6b7280', marginTop: 4 }}>
                      <strong>Target:</strong> {kpi.target} {kpi.unit}
                    </div>
                  )}
                </div>

                <div style={{ display: 'flex', gap: 8, marginLeft: 16 }}>
                  <button
                    className={approvals[kpi.kpi_id] === 'approved' ? 'btn-success' : 'btn-ghost'}
                    onClick={() => setStatus(kpi.kpi_id, 'approved')}
                  >
                    ✓ Approve
                  </button>
                  <button
                    className={approvals[kpi.kpi_id] === 'rejected' ? 'btn-danger' : 'btn-ghost'}
                    onClick={() => setStatus(kpi.kpi_id, 'rejected')}
                  >
                    ✗ Reject
                  </button>
                </div>
              </div>
            </div>
          ))}

          <button
            className="btn-primary"
            onClick={handleSubmit}
            disabled={saving}
            style={{ marginTop: 8 }}
          >
            {saving ? 'Saving…' : 'Save Approvals & Compute KPIs'}
          </button>
        </>
      )}
    </div>
  );
}
