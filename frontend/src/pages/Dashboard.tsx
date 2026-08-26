import { useQuery } from '@tanstack/react-query';
import {
  FlaskConical,
  CheckCircle2,
  Loader2,
  XCircle,
  Cpu,
  Gauge,
  HardDrive,
  Zap,
} from 'lucide-react';
import Header from '../components/Layout/Header';
import StatCard from '../components/Dashboard/StatCard';
import RecentExperiments from '../components/Dashboard/RecentExperiments';
import APIError from '../components/APIError';
import LoadingState from '../components/LoadingState';
import { getDashboardStats } from '../api/client';

export default function Dashboard() {
  const { data: stats, isLoading, isError, error, refetch } = useQuery({
    queryKey: ['dashboard-stats'],
    queryFn: getDashboardStats,
    retry: 2,
    staleTime: 30_000,
  });

  if (isLoading) {
    return (
      <div className="min-h-screen">
        <Header title="Dashboard" subtitle="Overview" />
        <LoadingState message="Loading dashboard..." />
      </div>
    );
  }

  if (isError || !stats) {
    return (
      <div className="min-h-screen">
        <Header title="Dashboard" subtitle="Overview" />
        <APIError
          title="Dashboard unavailable"
          error={error}
          onRetry={() => refetch()}
        />
      </div>
    );
  }

  return (
    <div className="min-h-screen">
      <Header title="Dashboard" subtitle="Overview" />

      <div className="p-8 space-y-8">
        {/* Hero Stats */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          <StatCard
            title="Total Experiments"
            value={stats.total_experiments}
            subtitle="All time"
            icon={FlaskConical}
            variant="quantum"
            trend={{ value: 12, isPositive: true }}
          />
          <StatCard
            title="Completed"
            value={stats.completed_experiments}
            subtitle={`${stats.total_experiments > 0 ? ((stats.completed_experiments / stats.total_experiments) * 100).toFixed(0) : 0}% success rate`}
            icon={CheckCircle2}
            variant="matrix"
          />
          <StatCard
            title="Running"
            value={stats.running_experiments}
            subtitle="Currently active"
            icon={Loader2}
            variant="neural"
          />
          <StatCard
            title="Failed"
            value={stats.failed_experiments}
            subtitle="Needs attention"
            icon={XCircle}
            variant="default"
          />
        </div>

        {/* Secondary Stats */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          <StatCard title="Models Tested" value={stats.total_models} icon={Cpu} />
          <StatCard
            title="Avg Compression"
            value={`${stats.avg_compression_ratio.toFixed(1)}x`}
            subtitle="Across all experiments"
            icon={HardDrive}
          />
          <StatCard
            title="Avg Perplexity"
            value={stats.avg_perplexity.toFixed(2)}
            subtitle="WikiText-2 test"
            icon={Gauge}
          />
          <StatCard
            title="GPU Utilization"
            value="—"
            subtitle="Run experiments to populate"
            icon={Zap}
          />
        </div>

        {/* Recent Experiments + Placeholder */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <RecentExperiments experiments={stats.recent_experiments ?? []} />
          <div className="bg-white border border-[#e5e5e5] p-8 flex flex-col items-center justify-center text-center min-h-[300px]">
            <Gauge className="w-10 h-10 text-[#e5e5e5] mb-4" />
            <p className="font-display text-xl text-black mb-2">Metrics Visualization</p>
            <p className="text-[11px] text-[#999]">
              Charts will populate once experiments produce metrics.
            </p>
            <div className="gold-accent mt-4" />
          </div>
        </div>

        {/* Quick Actions */}
        <div>
          <p className="section-label mb-2">Quick Actions</p>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <QuickAction title="New AWQ Experiment" description="4-bit weight quantization" accent="black" />
            <QuickAction title="New GPTQ Experiment" description="Hessian-based quantization" accent="gold" />
            <QuickAction title="Compare Methods" description="Side-by-side analysis" accent="gray" />
            <QuickAction title="Generate Report" description="AI-powered insights" accent="gold" />
          </div>
        </div>
      </div>
    </div>
  );
}

function QuickAction({ title, description, accent }: { title: string; description: string; accent: 'black' | 'gold' | 'gray' }) {
  const borders = {
    black: 'border-l-2 border-l-black hover:bg-[#fafafa]',
    gold: 'border-l-2 border-l-[#c5a47e] hover:bg-[#faf6f0]',
    gray: 'border-l-2 border-l-[#666] hover:bg-[#fafafa]',
  };

  return (
    <button className={`p-5 border border-[#e5e5e5] bg-white text-left transition-all duration-300 ${borders[accent]}`}>
      <h4 className="font-display text-base text-black">{title}</h4>
      <p className="text-[11px] text-[#999] mt-1">{description}</p>
    </button>
  );
}
