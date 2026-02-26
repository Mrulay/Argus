import { useState } from 'react';
import { createProject, uploadDataset, createJob } from '../api/client';

export default function UploadPage() {
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState('');
  const [error, setError] = useState('');

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!name || !description || !file) {
      setError('Please fill in all fields and select a file.');
      return;
    }
    setLoading(true);
    setError('');
    setSuccess('');
    try {
      const project = await createProject({ name, business_description: description });
      const dataset = await uploadDataset(project.project_id, file);
      const job = await createJob(project.project_id, 'profile', dataset.dataset_id);
      localStorage.setItem('argus_project_id', project.project_id);
      localStorage.setItem('argus_dataset_id', dataset.dataset_id);
      localStorage.setItem('argus_job_id', job.job_id);
      setSuccess(
        `Project "${project.name}" created. Profiling job started (ID: ${job.job_id}). ` +
        `Navigate to KPI Approval once the job completes.`
      );
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div>
      <div className="page-header">
        <h1>Upload Data</h1>
        <p>Upload your CSV or Excel file and describe your business to get started.</p>
      </div>

      <div className="card" style={{ maxWidth: 560 }}>
        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <div>
            <label style={{ display: 'block', fontWeight: 600, marginBottom: 6 }}>Project Name</label>
            <input
              type="text"
              placeholder="e.g. Q2 Revenue Analysis"
              value={name}
              onChange={e => setName(e.target.value)}
            />
          </div>

          <div>
            <label style={{ display: 'block', fontWeight: 600, marginBottom: 6 }}>Business Description</label>
            <textarea
              rows={4}
              placeholder="Briefly describe your business model, industry, and what you sell..."
              value={description}
              onChange={e => setDescription(e.target.value)}
              style={{ resize: 'vertical' }}
            />
          </div>

          <div>
            <label style={{ display: 'block', fontWeight: 600, marginBottom: 6 }}>
              Dataset (CSV or XLSX)
            </label>
            <input
              type="file"
              accept=".csv,.xlsx,.xls"
              style={{ padding: '6px 0', border: 'none' }}
              onChange={e => setFile(e.target.files?.[0] ?? null)}
            />
          </div>

          {error && <div className="error-msg">{error}</div>}
          {success && <div className="info-msg">{success}</div>}

          <button type="submit" className="btn-primary" disabled={loading}>
            {loading ? 'Uploading…' : 'Upload & Start Analysis'}
          </button>
        </form>
      </div>

      <div className="card" style={{ maxWidth: 560, background: '#f9fafb' }}>
        <h3 style={{ margin: '0 0 8px', fontSize: 14, color: '#6b7280' }}>How it works</h3>
        <ol style={{ margin: 0, paddingLeft: 20, fontSize: 14, color: '#6b7280', lineHeight: 1.8 }}>
          <li>Upload your CSV/XLSX and describe your business</li>
          <li>The platform profiles your data and uses AI to propose KPIs</li>
          <li>You review and approve the KPI definitions (<strong>required</strong>)</li>
          <li>KPIs are computed and a consultant-style report is generated</li>
          <li>Review risks, compliance notes, forecasts, and recommendations</li>
        </ol>
      </div>
    </div>
  );
}
