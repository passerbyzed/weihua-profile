import { BrowserRouter, Route, Routes } from 'react-router-dom';
import Layout from './components/Layout';
import { MachineProvider } from './state/machine';
import DashboardPage from './pages/DashboardPage';
import IssuesPage from './pages/IssuesPage';
import IssuesAskPage from './pages/IssuesAskPage';
import IssueDetailPage from './pages/IssueDetailPage';
import KbPage from './pages/KbPage';
import KbCheckPage from './pages/KbCheckPage';
import AlertsPage from './pages/AlertsPage';
import AlertConfigPage from './pages/AlertConfigPage';

export default function App() {
  return (
    <BrowserRouter>
      <MachineProvider>
        <Layout>
          <Routes>
            <Route path="/" element={<DashboardPage />} />
            <Route path="/issues" element={<IssuesPage />} />
            <Route path="/issues/ask" element={<IssuesAskPage />} />
            <Route path="/issues/:id" element={<IssueDetailPage />} />
            <Route path="/kb" element={<KbPage />} />
            <Route path="/kb/check" element={<KbCheckPage />} />
            <Route path="/alerts" element={<AlertsPage />} />
            <Route path="/alerts/config" element={<AlertConfigPage />} />
          </Routes>
        </Layout>
      </MachineProvider>
    </BrowserRouter>
  );
}
