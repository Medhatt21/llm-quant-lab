import { useState } from 'react';
import { 
  Layers,
  BarChart3,
  Download,
  Filter,
  FlaskConical,
  TrendingUp,
  Activity,
  Zap,
} from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import Header from '../components/Layout/Header';
import APIError from '../components/APIError';
import LoadingState from '../components/LoadingState';
import { getExperiments, getAnalyticsData } from '../api/client';
import PerplexityChart from '../components/Charts/PerplexityChart';
import ParetoChart from '../components/Charts/ParetoChart';
import LayerStatsChart from '../components/Charts/LayerStatsChart';

export default function Analytics() {
  const [activeTab, setActiveTab] = useState<'overview' | 'perplexity' | 'pareto' | 'layers'>('overview');

  const { data: expData, isLoading, isError, error, refetch } = useQuery({
    queryKey: ['analytics-experiments'],
    queryFn: () => getExperiments({ limit: 100, status: 'completed' }),
    retry: 2,
  });

  const { data: analyticsData } = useQuery({
    queryKey: ['analytics-data'],
    queryFn: getAnalyticsData,
    retry: 1,
  });

  if (isLoading) {
    return (
      <div className="min-h-screen">
        <Header title="Analytics" subtitle="Visualize and compare quantization results" />
        <LoadingState message="Loading analytics data..." />
      </div>
    );
  }

  if (isError || !expData) {
    return (
      <div className="min-h-screen">
        <Header title="Analytics" subtitle="Visualize and compare quantization results" />
        <APIError title="Could not load analytics data" error={error} onRetry={() => refetch()} />
      </div>
    );
  }

  const experiments = expData.experiments;
  const hasData = experiments.length > 0;
  const perplexityData = analyticsData?.perplexity_data || [];
  const paretoData = analyticsData?.pareto_data || [];
  const layerData = analyticsData?.layer_data || [];

  const layerStatsData = buildLayerStatsData(layerData);

  const tabs = [
    { id: 'overview' as const, label: 'Overview', icon: BarChart3 },
    { id: 'perplexity' as const, label: 'Perplexity', icon: TrendingUp },
    { id: 'pareto' as const, label: 'Pareto Front', icon: Activity },
    { id: 'layers' as const, label: 'Layer Analysis', icon: Layers },
  ];

  return (
    <div className="min-h-screen">
      <Header 
        title="Analytics" 
        subtitle="Visualize and compare quantization results"
      />

      <div className="p-6 space-y-6">
        {/* Toolbar */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            {tabs.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`flex items-center gap-2 px-4 py-2 text-sm font-medium transition-colors ${
                  activeTab === tab.id
                    ? 'bg-black text-white'
                    : 'bg-white border border-[#e5e5e5] text-[#666] hover:text-black hover:border-[#999]'
                }`}
              >
                <tab.icon className="w-4 h-4" />
                {tab.label}
              </button>
            ))}
          </div>
          <div className="flex items-center gap-2">
            <button className="flex items-center gap-2 px-4 py-2 bg-white border border-[#e5e5e5] text-sm text-[#666] hover:text-black hover:border-[#999] transition-colors">
              <Filter className="w-4 h-4" /> Filter Methods
            </button>
            <button className="flex items-center gap-2 px-4 py-2 bg-[#f5f5f5] hover:bg-[#e5e5e5] text-black text-sm transition-colors">
              <Download className="w-4 h-4" /> Export Data
            </button>
          </div>
        </div>

        {!hasData ? (
          <div className="bg-white border-0 border border-[#e5e5e5] p-12 text-center">
            <BarChart3 className="w-16 h-16 text-[#ccc] mx-auto mb-4" />
            <h2 className="text-lg font-display font-semibold text-black mb-2">No completed experiments yet</h2>
            <p className="text-sm text-[#999] mb-6 max-w-md mx-auto">
              Analytics visualizations are populated from real experiment results.
              Run at least one experiment to see Pareto frontiers, perplexity comparisons, throughput charts, and layer-wise analysis.
            </p>
            <div className="bg-[#fafafa] rounded-none p-4 inline-block text-left text-sm text-[#666]">
              <p className="text-black font-mono mb-2">Quick start:</p>
              <code className="block text-black font-mono text-xs">
                python -m src.main run-experiment \<br />
                &nbsp;&nbsp;--model-path facebook/opt-125m \<br />
                &nbsp;&nbsp;--quant-techs awq --bit-width 4
              </code>
            </div>
          </div>
        ) : (
          <>
            {/* Summary Cards */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <SummaryCard 
                icon={<FlaskConical className="w-5 h-5 text-black" />}
                title="Completed Experiments" 
                value={String(experiments.length)} 
                subtitle="Available for analysis" 
              />
              <SummaryCard 
                icon={<Layers className="w-5 h-5 text-[#666]" />}
                title="Unique Models" 
                value={String(new Set(experiments.map(e => e.model_name)).size)} 
                subtitle="Across experiments" 
              />
              <SummaryCard 
                icon={<TrendingUp className="w-5 h-5 text-[#2D8A4E]" />}
                title="Perplexity Points" 
                value={String(perplexityData.length)} 
                subtitle="Measurements" 
              />
              <SummaryCard 
                icon={<Zap className="w-5 h-5 text-[#C5A47E]" />}
                title="GPU Types" 
                value={String(new Set(experiments.filter(e => e.gpu_type).map(e => e.gpu_type)).size)} 
                subtitle="Hardware platforms" 
              />
            </div>

            {/* Charts */}
            {(activeTab === 'overview' || activeTab === 'perplexity') && (
              <div>
                {perplexityData.length > 0 ? (
                  <PerplexityChart data={perplexityData} />
                ) : (
                  <EmptyChart title="Perplexity vs Bit Width" message="No perplexity metrics recorded yet. Complete an experiment with evaluation enabled." />
                )}
              </div>
            )}

            {(activeTab === 'overview' || activeTab === 'pareto') && (
              <div>
                {paretoData.length > 0 ? (
                  <ParetoChart data={paretoData} xMetric="compression_ratio" />
                ) : (
                  <EmptyChart title="Pareto Front Analysis" message="Need experiments with both perplexity and hardware stats for Pareto analysis." />
                )}
              </div>
            )}

            {(activeTab === 'overview' || activeTab === 'layers') && (
              <div>
                {layerStatsData.length > 0 ? (
                  <LayerStatsChart data={layerStatsData} metric="error" />
                ) : (
                  <EmptyChart title="Layer-wise Analysis" message="No layer metrics recorded yet. Enable layer-level logging in your next experiment." />
                )}
              </div>
            )}

            {/* Experiments table */}
            <div className="bg-white border-0 border border-[#e5e5e5] overflow-hidden">
              <div className="px-5 py-4 border-b border-[#e5e5e5]">
                <h3 className="font-display font-semibold text-black flex items-center gap-2">
                  <Layers className="w-5 h-5 text-black" />
                  Completed Experiments
                </h3>
                <p className="text-xs text-[#999] mt-1">Data source for all charts above.</p>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead>
                    <tr className="border-b border-[#e5e5e5]">
                      <th className="px-5 py-3 text-left text-xs font-medium text-[#999] uppercase">Experiment</th>
                      <th className="px-5 py-3 text-left text-xs font-medium text-[#999] uppercase">Model</th>
                      <th className="px-5 py-3 text-left text-xs font-medium text-[#999] uppercase">Hardware</th>
                      <th className="px-5 py-3 text-left text-xs font-medium text-[#999] uppercase">Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#e5e5e5]">
                    {experiments.slice(0, 20).map((exp) => (
                      <tr key={exp.id} className="hover:bg-[#fafafa]">
                        <td className="px-5 py-4 text-black font-medium">{exp.name || `#${exp.id}`}</td>
                        <td className="px-5 py-4 text-[#666] font-mono text-xs">{exp.model_name}</td>
                        <td className="px-5 py-4 text-[#666]">{exp.gpu_type || '\u2014'}</td>
                        <td className="px-5 py-4"><span className="text-[#2D8A4E] text-sm">{exp.status}</span></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Paper export hint */}
            <div className="bg-[#fafafa] border border-[#e5e5e5] p-5 flex items-start gap-4">
              <FlaskConical className="w-6 h-6 text-[#C5A47E] shrink-0 mt-0.5" />
              <div className="text-sm">
                <p className="text-black font-medium mb-1">Generate paper-grade charts</p>
                <p className="text-[#999]">
                  Use the CLI to export publication-quality plots and LaTeX tables from these experiments:
                </p>
                <code className="block mt-2 px-3 py-2 bg-[#fafafa] rounded text-black font-mono text-xs">
                  python -m src.main paper-export --experiment-ids {experiments.slice(0, 5).map(e => e.id).join(',')} --formats latex,plots
                </code>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

function SummaryCard({ icon, title, value, subtitle }: { icon: React.ReactNode; title: string; value: string; subtitle: string }) {
  return (
    <div className="bg-white border-0 border border-[#e5e5e5] p-5">
      <div className="flex items-center gap-3 mb-2">
        {icon}
        <p className="text-sm text-[#999]">{title}</p>
      </div>
      <p className="text-2xl font-display font-bold text-black mt-1">{value}</p>
      <p className="text-xs text-[#999] mt-1">{subtitle}</p>
    </div>
  );
}

function EmptyChart({ title, message }: { title: string; message: string }) {
  return (
    <div className="bg-white border-0 border border-[#e5e5e5] p-8 text-center">
      <BarChart3 className="w-10 h-10 text-[#ccc] mx-auto mb-3" />
      <h3 className="font-display font-semibold text-black mb-1">{title}</h3>
      <p className="text-sm text-[#999]">{message}</p>
    </div>
  );
}

function buildLayerStatsData(layerData: Array<{ layer_index: number; layer_name: string; stat_name: string; value: number }>) {
  const layerMap = new Map<number, {
    layer_index: number;
    layer_name: string;
    pre_quant_norm: number;
    post_quant_norm: number;
    quantization_error: number;
  }>();

  for (const item of layerData) {
    if (!layerMap.has(item.layer_index)) {
      layerMap.set(item.layer_index, {
        layer_index: item.layer_index,
        layer_name: item.layer_name,
        pre_quant_norm: 0,
        post_quant_norm: 0,
        quantization_error: 0,
      });
    }
    const entry = layerMap.get(item.layer_index)!;
    if (item.stat_name === 'pre_quant_norm' || item.stat_name === 'weight_norm') {
      entry.pre_quant_norm = item.value;
    } else if (item.stat_name === 'post_quant_norm' || item.stat_name === 'quantized_weight_norm') {
      entry.post_quant_norm = item.value;
    } else if (item.stat_name === 'quantization_error' || item.stat_name === 'mse' || item.stat_name === 'error') {
      entry.quantization_error = item.value;
    }
  }

  return Array.from(layerMap.values()).sort((a, b) => a.layer_index - b.layer_index);
}
