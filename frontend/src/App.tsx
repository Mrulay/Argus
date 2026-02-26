import { useEffect, useMemo, useState } from 'react';
import { BrowserRouter, Routes, Route, NavLink, useLocation, useNavigate } from 'react-router-dom';
import UploadPage from './pages/UploadPage';
import KPIApprovalPage from './pages/KPIApprovalPage';
import DashboardPage from './pages/DashboardPage';
import ReportPage from './pages/ReportPage';
import { listProjects, type Project } from './api/client';

function ProjectSelector() {
  const navigate = useNavigate();
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [selectedId, setSelectedId] = useState(
    localStorage.getItem('argus_project_id') ?? ''
  );

  useEffect(() => {
    listProjects()
      .then(setProjects)
      .catch(err => setError(String(err)))
      .finally(() => setLoading(false));
  }, []);

  const options = useMemo(() => projects.slice().sort(
    (a, b) => b.created_at.localeCompare(a.created_at)
  ), [projects]);

  function handleChange(value: string) {
    setSelectedId(value);
    if (value) {
      localStorage.setItem('argus_project_id', value);
      localStorage.removeItem('argus_dataset_id');
      localStorage.removeItem('argus_dataset_ids');
      navigate('/dashboard');
    }
  }

  return (
    <div className="project-selector">
      <div className="selector-label">Project</div>
      {loading ? (
        <div className="selector-muted">Loading projects…</div>
      ) : error ? (
        <div className="selector-error">{error}</div>
      ) : (
        <select
          value={selectedId}
          onChange={e => handleChange(e.target.value)}
          className="project-select"
        >
          <option value="">Select a project</option>
          {options.map(project => (
            <option key={project.project_id} value={project.project_id}>
              {project.name}
            </option>
          ))}
        </select>
      )}
      <button
        type="button"
        className="project-add"
        onClick={() => navigate('/')}
      >
        + New project
      </button>
    </div>
  );
}

function Sidebar() {
  return (
    <aside className="sidebar">
      <div className="sidebar-brand">
        <div className="brand-mark">A</div>
        <div>
          <div className="brand-name">Argus</div>
          <div className="brand-sub">KPI Advisory Portal</div>
        </div>
      </div>

      <nav className="sidebar-nav">
        <NavLink to="/kpis" className={({ isActive }) => isActive ? 'active' : ''}>
          KPI Approval
        </NavLink>
        <NavLink to="/dashboard" className={({ isActive }) => isActive ? 'active' : ''}>
          Dashboard
        </NavLink>
        <NavLink to="/report" className={({ isActive }) => isActive ? 'active' : ''}>
          Report
        </NavLink>
      </nav>

      <div className="sidebar-footer">
        <ProjectSelector />
      </div>
    </aside>
  );
}

function AppShell() {
  const location = useLocation();
  const isOnboarding = location.pathname === '/';

  if (isOnboarding) {
    return (
      <div className="onboarding-shell">
        <UploadPage />
      </div>
    );
  }

  return (
    <div className="app-shell">
      <Sidebar />
      <main className="content">
        <Routes>
          <Route path="/kpis" element={<KPIApprovalPage />} />
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/report" element={<ReportPage />} />
        </Routes>
      </main>
    </div>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/*" element={<AppShell />} />
      </Routes>
    </BrowserRouter>
  );
}
