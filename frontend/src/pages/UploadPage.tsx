import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { createProject, uploadDataset, uploadDatasets, createJob } from '../api/client';

export default function UploadPage() {
  const navigate = useNavigate();
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [files, setFiles] = useState<File[]>([]);
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState('');
  const [error, setError] = useState('');

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!name || !description || files.length === 0) {
      setError('Please fill in all fields and select at least one file.');
      return;
    }
    setLoading(true);
    setError('');
    setSuccess('');
    try {
      const project = await createProject({ name, business_description: description });
      const datasets = files.length === 1
        ? [await uploadDataset(project.project_id, files[0])]
        : await uploadDatasets(project.project_id, files);
      const datasetIds = datasets.map(d => d.dataset_id);
      const job = await createJob(
        project.project_id,
        'profile',
        datasets.length === 1 ? datasets[0].dataset_id : undefined
      );
      localStorage.setItem('argus_project_id', project.project_id);
      if (datasets.length === 1) {
        localStorage.setItem('argus_dataset_id', datasets[0].dataset_id);
        localStorage.removeItem('argus_dataset_ids');
      } else {
        localStorage.removeItem('argus_dataset_id');
        localStorage.setItem('argus_dataset_ids', JSON.stringify(datasetIds));
      }
      localStorage.setItem('argus_job_id', job.job_id);
      setSuccess(
        `Project "${project.name}" created. Uploaded ${datasets.length} file(s). ` +
        `Profiling job started (ID: ${job.job_id}). Navigate to KPI Approval once it completes.`
      );
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="onboarding">
      <header className="onboarding-hero">
        <div className="hero-eyebrow">Onboarding</div>
        <h1>Turn raw retail data into an executive KPI portal.</h1>
        <p>
          Create a project, upload your CSV or Excel files, and let Argus profile the data and
          propose KPIs. Once the project is ready, enter the portal to review approvals and reports.
        </p>
        <button
          type="button"
          className="btn-secondary"
          onClick={() => navigate('/dashboard')}
          style={{ marginTop: 16 }}
        >
          Go to Portal
        </button>
      </header>

      <div className="onboarding-grid">
        <div className="card onboarding-card">
          <h2>Create a project</h2>
          <p className="muted">Give your project a name, describe the business, and upload data.</p>
          <form onSubmit={handleSubmit} className="form-grid">
            <div>
              <label>Project Name</label>
              <input
                type="text"
                placeholder="e.g. Department Store Performance"
                value={name}
                onChange={e => setName(e.target.value)}
              />
            </div>

            <div>
              <label>Business Description</label>
              <textarea
                rows={4}
                placeholder="Describe your business model, regions, and what matters most..."
                value={description}
                onChange={e => setDescription(e.target.value)}
              />
            </div>

            <div>
              <label>Dataset(s) (CSV or XLSX)</label>
              <input
                type="file"
                accept=".csv,.xlsx,.xls"
                multiple
                onChange={e => setFiles(Array.from(e.target.files ?? []))}
              />
              {files.length > 0 && (
                <div className="file-pill">{files.length} file(s) ready</div>
              )}
            </div>

            {error && <div className="error-msg">{error}</div>}
            {success && <div className="info-msg">{success}</div>}

            <div className="form-actions">
              <button type="submit" className="btn-primary" disabled={loading}>
                {loading ? 'Uploading…' : 'Create Project'}
              </button>
              {success && (
                <button
                  type="button"
                  className="btn-secondary"
                  onClick={() => navigate('/kpis')}
                >
                  Enter Portal
                </button>
              )}
            </div>
          </form>
        </div>

        <div className="onboarding-panel">
          <div className="panel-card">
            <h3>What happens next</h3>
            <ol>
              <li>We profile your dataset for joins, dates, and missingness.</li>
              <li>AI drafts KPI definitions with formulas and rationale.</li>
              <li>You approve KPIs before computation begins.</li>
              <li>A report is generated with risks and recommendations.</li>
            </ol>
          </div>
          <div className="panel-card accent">
            <h3>Quick tips</h3>
            <ul>
              <li>Upload multiple CSVs if they share the same schema.</li>
              <li>Include a clear date column for trend KPIs.</li>
              <li>Use descriptive column names for better KPI suggestions.</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
}
