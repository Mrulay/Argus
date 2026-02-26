import { BrowserRouter, Routes, Route, NavLink } from 'react-router-dom';
import UploadPage from './pages/UploadPage';
import KPIApprovalPage from './pages/KPIApprovalPage';
import DashboardPage from './pages/DashboardPage';
import ReportPage from './pages/ReportPage';

export default function App() {
  return (
    <BrowserRouter>
      <nav>
        <span className="logo">Argus</span>
        <NavLink to="/" end className={({ isActive }) => isActive ? 'active' : ''}>Upload</NavLink>
        <NavLink to="/kpis" className={({ isActive }) => isActive ? 'active' : ''}>KPI Approval</NavLink>
        <NavLink to="/dashboard" className={({ isActive }) => isActive ? 'active' : ''}>Dashboard</NavLink>
        <NavLink to="/report" className={({ isActive }) => isActive ? 'active' : ''}>Report</NavLink>
      </nav>
      <div className="container">
        <Routes>
          <Route path="/" element={<UploadPage />} />
          <Route path="/kpis" element={<KPIApprovalPage />} />
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/report" element={<ReportPage />} />
        </Routes>
      </div>
    </BrowserRouter>
  );
}
