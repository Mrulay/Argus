import { useEffect, useState } from 'react';
import { listKPIs, approveKPIs, createCustomKPI, type KPI, type KPIStatus } from '../api/client';

export default function KPIApprovalPage() {
  const projectId = localStorage.getItem('argus_project_id') ?? '';
  const [kpis, setKpis] = useState<KPI[]>([]);
  const [approvals, setApprovals] = useState<Record<string, KPIStatus>>({});
  const [loading, setLoading] = useState(true);
  const [polling, setPolling] = useState(false);
  const [saving, setSaving] = useState(false);
  const [adding, setAdding] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [customRequest, setCustomRequest] = useState('');
  const [customError, setCustomError] = useState('');
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  useEffect(() => {
    if (!projectId) return;
    let interval: number | undefined;

    const fetchKpis = () => {
      listKPIs(projectId)
        .then(data => {
          setKpis(data);
          const initial: Record<string, KPIStatus> = {};
          data.forEach(k => { initial[k.kpi_id] = k.status; });
          setApprovals(initial);
          if (data.length > 0) {
            setPolling(false);
            if (interval) window.clearInterval(interval);
          } else {
            setPolling(true);
          }
        })
        .catch(err => setError(String(err)))
        .finally(() => setLoading(false));
    };

    fetchKpis();
    interval = window.setInterval(fetchKpis, 2000);

    return () => {
      if (interval) window.clearInterval(interval);
    };
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

  async function handleAddCustomKPI() {
    if (!customRequest.trim()) {
      setCustomError('Please enter a KPI request.');
      return;
    }
    setAdding(true);
    setCustomError('');
    try {
      const kpi = await createCustomKPI(projectId, customRequest.trim());
      setKpis(prev => [...prev, kpi]);
      setApprovals(prev => ({ ...prev, [kpi.kpi_id]: kpi.status }));
      setCustomRequest('');
      setModalOpen(false);
    } catch (err: unknown) {
      setCustomError(err instanceof Error ? err.message : String(err));
    } finally {
      setAdding(false);
    }
  }

  function setStatus(kpiId: string, status: KPIStatus) {
    setApprovals(prev => ({ ...prev, [kpiId]: status }));
  }

  if (!projectId) return <div className="error-msg">No active project. Please upload data first.</div>;
  if (loading) {
    return (
      <div className="loading-state">
        <div className="loading-orbit" />
        <div className="loading-text">Loading KPI proposals…</div>
      </div>
    );
  }

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
        <div className="loading-state">
          <div className="loading-orbit" />
          <div className="loading-text">
            {polling ? 'Waiting for KPI recommendations…' : 'No KPI proposals yet.'}
          </div>
        </div>
      ) : (
        <>
          {kpis.map(kpi => (
            <div className="card fade-in" key={kpi.kpi_id}>
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

          <button
            className="btn-ghost"
            onClick={() => setModalOpen(true)}
            style={{ marginTop: 12 }}
          >
            + Add KPI
          </button>
        </>
      )}

      {modalOpen && (
        <div className="modal-backdrop" onClick={() => setModalOpen(false)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <h2>Add a custom KPI</h2>
            <p className="muted">Describe the KPI you want in plain language.</p>
            <textarea
              rows={4}
              placeholder="e.g., Revenue share by product category for the last 30 days"
              value={customRequest}
              onChange={e => setCustomRequest(e.target.value)}
            />
            {customError && <div className="error-msg" style={{ marginTop: 12 }}>{customError}</div>}
            <div className="form-actions" style={{ marginTop: 16 }}>
              <button className="btn-secondary" onClick={() => setModalOpen(false)}>
                Cancel
              </button>
              <button className="btn-primary" onClick={handleAddCustomKPI} disabled={adding}>
                {adding ? 'Adding…' : 'Add KPI'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
