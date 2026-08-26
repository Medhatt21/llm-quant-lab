import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BackgroundTasksProvider } from './context/BackgroundTasks';
import Layout from './components/Layout';
import Dashboard from './pages/Dashboard';
import { ExperimentsList, ExperimentDetail, NewExperiment } from './pages/Experiments';
import Analytics from './pages/Analytics';
import Methods from './pages/Methods';
import Reports from './pages/Reports';
import KnowledgeGraph from './pages/KnowledgeGraph';
import ModelBrowser from './pages/ModelBrowser';
import ScientistAnalysis from './pages/ScientistAnalysis';
import Papers from './pages/Papers';
import ReproductionSummary from './pages/ReproductionSummary';
import HealthCheck from './pages/HealthCheck';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 60 * 5, // 5 minutes
      retry: 1,
    },
  },
});

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BackgroundTasksProvider>
        <BrowserRouter>
          <div>
            <Routes>
              <Route path="/" element={<Layout />}>
                <Route index element={<Dashboard />} />
                <Route path="experiments" element={<ExperimentsList />} />
                <Route path="experiments/new" element={<NewExperiment />} />
                <Route path="experiments/:id" element={<ExperimentDetail />} />
                <Route path="models" element={<ModelBrowser />} />
                <Route path="knowledge-graph" element={<KnowledgeGraph />} />
                <Route path="analytics" element={<Analytics />} />
                <Route path="scientist" element={<ScientistAnalysis />} />
                <Route path="methods" element={<Methods />} />
                <Route path="reports" element={<Reports />} />
                <Route path="papers" element={<Papers />} />
                <Route path="reproduction" element={<ReproductionSummary />} />
                <Route path="health" element={<HealthCheck />} />
                <Route path="settings" element={<ComingSoon title="Settings" />} />
              </Route>
            </Routes>
          </div>
        </BrowserRouter>
      </BackgroundTasksProvider>
    </QueryClientProvider>
  );
}

function ComingSoon({ title }: { title: string }) {
  return (
    <div className="min-h-screen flex items-center justify-center">
      <div className="text-center">
        <h1 className="text-3xl font-display font-bold text-black mb-2">{title}</h1>
        <p className="text-gray-500">Coming soon...</p>
      </div>
    </div>
  );
}

export default App;
