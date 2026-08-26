import { useParams, Link, useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useRef, useEffect, useState } from 'react';
import {
  ArrowLeft, Brain, CheckCircle2, Clock, Cpu, Database,
  ExternalLink, FileText, Fingerprint, Gauge, Hash, Layers,
  Loader2, Trash2, Play, RefreshCw, Zap, GitBranch, Tag,
  Terminal, ChevronDown, ChevronUp, Lightbulb, FlaskConical, BarChart3,
} from 'lucide-react';
import clsx from 'clsx';
import { format } from 'date-fns';
import Header from '../../components/Layout/Header';
import APIError from '../../components/APIError';
import LoadingState from '../../components/LoadingState';
import { getExperiment, getExperimentStatus, getExperimentLogs, launchExperiment, deleteExperiment } from '../../api/client';
import { useBackgroundTasks } from '../../context/BackgroundTasks';

export default function ExperimentDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const experimentId = Number(id);
  const { tasks, startReport, startUltimateReport, dismiss: dismissTask } = useBackgroundTasks();

  const expTasks = tasks.filter((t) => t.experimentId === experimentId);
  const reportTask = expTasks.find((t) => t.kind === 'report' && t.status === 'running');
  const ultimateTask = expTasks.find((t) => t.kind === 'ultimate-report');
  const ultimateRunning = expTasks.some((t) => t.kind === 'ultimate-report' && t.status === 'running');
  const ultimateResult = ultimateTask?.status === 'completed' && ultimateTask.result
    ? (ultimateTask.result as {
        question: string;
        findings: Array<{ title: string; description: string; evidence: string; confidence: number; category: string }>;
        follow_up_experiments: Array<{ description: string; rationale: string; priority: number; config?: Record<string, unknown> }>;
        raw_reasoning: string;
        plots: string[];
        tool_calls_count: number;
        thinking_turns: number;
      })
    : null;

  const rerunMutation = useMutation({
    mutationFn: () => launchExperiment(experimentId),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['experiment', experimentId] }); },
    onError: (err) => alert(`Re-run failed: ${err instanceof Error ? err.message : err}`),
  });

  const deleteMutation = useMutation({
    mutationFn: () => deleteExperiment(experimentId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['experiments'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard-stats'] });
      navigate('/experiments');
    },
    onError: (err) => alert(`Delete failed: ${err instanceof Error ? err.message : err}`),
  });

  const { data: detail, isLoading, isError, error, refetch } = useQuery({
    queryKey: ['experiment', experimentId],
    queryFn: () => getExperiment(experimentId),
    enabled: !isNaN(experimentId),
    retry: 2,
  });

  const [logsExpanded, setLogsExpanded] = useState(true);
  const isRunningOrPending = detail?.experiment?.status === 'running' || detail?.experiment?.status === 'pending';

  const { data: statusData } = useQuery({
    queryKey: ['experiment-status', experimentId],
    queryFn: async () => {
      const status = await getExperimentStatus(experimentId);
      if (status.status !== detail?.experiment?.status) refetch();
      return status;
    },
    enabled: !isNaN(experimentId) && isRunningOrPending,
    refetchInterval: isRunningOrPending ? 3000 : false,
  });

  const { data: logsData } = useQuery({
    queryKey: ['experiment-logs', experimentId],
    queryFn: () => getExperimentLogs(experimentId, 0, 500),
    enabled: !isNaN(experimentId),
    refetchInterval: isRunningOrPending ? 2000 : false,
  });

  const logsEndRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (logsEndRef.current && logsExpanded) logsEndRef.current.scrollIntoView({ behavior: 'smooth' });
  }, [logsData?.logs, logsExpanded]);

  if (isLoading) return (<div className="min-h-screen"><Header title={`Experiment #${id}`} subtitle="Loading" /><LoadingState message="Loading experiment details..." /></div>);
  if (isError || !detail) return (<div className="min-h-screen"><Header title={`Experiment #${id}`} subtitle="Error" /><APIError title={`Could not load experiment #${id}`} error={error} onRetry={() => refetch()} /></div>);

  const exp = detail.experiment;

  return (
    <div className="min-h-screen">
      <Header title={exp.name ? `#${exp.id} \u2014 ${exp.name}` : `Experiment #${exp.id}`} subtitle={exp.model_name} />
      <div className="p-8 space-y-6">
        {/* Breadcrumb & Actions */}
        <div className="flex items-center justify-between">
          <Link to="/experiments" className="flex items-center gap-2 text-[11px] font-semibold tracking-[0.1em] uppercase text-[#666] hover:text-black transition-colors">
            <ArrowLeft className="w-4 h-4" /> Back to Experiments
          </Link>
          <div className="flex items-center gap-3">
            <button onClick={() => rerunMutation.mutate()} disabled={rerunMutation.isPending || exp?.status === 'running' || detail.quant_configs.length === 0}
              className="flex items-center gap-2 px-4 py-2.5 bg-[#f5f5f5] hover:bg-[#e5e5e5] disabled:opacity-40 text-black text-[11px] font-semibold tracking-[0.1em] uppercase transition-colors">
              <RefreshCw className={clsx('w-4 h-4', rerunMutation.isPending && 'animate-spin')} />
              {rerunMutation.isPending ? 'Launching...' : 'Re-run'}
            </button>
            <button onClick={() => startReport(experimentId)} disabled={!!reportTask}
              className="flex items-center gap-2 px-4 py-2.5 bg-[#f5f5f5] hover:bg-[#e5e5e5] disabled:opacity-40 text-black text-[11px] font-semibold tracking-[0.1em] uppercase transition-colors">
              {reportTask ? <Loader2 className="w-4 h-4 animate-spin" /> : <FileText className="w-4 h-4" />}
              {reportTask ? 'Generating...' : 'Generate Report'}
            </button>
            <button onClick={() => startUltimateReport(experimentId)} disabled={ultimateRunning}
              className="flex items-center gap-2 px-5 py-2.5 bg-black hover:bg-[#1a1a1a] disabled:opacity-40 text-white text-[11px] font-semibold tracking-[0.15em] uppercase transition-colors">
              {ultimateRunning ? <Loader2 className="w-4 h-4 animate-spin" /> : <Brain className="w-4 h-4" />}
              {ultimateRunning ? 'Analyzing...' : 'Ultimate Analysis'}
            </button>
            <button onClick={() => { if (confirm('Delete this experiment?')) deleteMutation.mutate(); }} disabled={deleteMutation.isPending}
              className="p-2.5 bg-[#f5f5f5] hover:bg-[#fef2f2] hover:text-[#dc2626] text-[#999] transition-colors">
              <Trash2 className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Status Banner */}
        <div className={clsx('flex items-center gap-4 p-5 border border-[#e5e5e5]',
          exp.status === 'completed' && 'border-l-2 border-l-[#22c55e] bg-[#fafafa]',
          exp.status === 'running' && 'border-l-2 border-l-[#c5a47e] bg-[#faf6f0]',
          exp.status === 'failed' && 'border-l-2 border-l-[#dc2626] bg-[#fafafa]',
          exp.status === 'pending' && 'border-l-2 border-l-[#999] bg-[#fafafa]')}>
          <div className="p-3 bg-white border border-[#e5e5e5]">
            {exp.status === 'running' ? <RefreshCw className="w-5 h-5 text-[#c5a47e] animate-spin" /> :
              <CheckCircle2 className={clsx('w-5 h-5', exp.status === 'completed' && 'text-[#22c55e]', exp.status === 'failed' && 'text-[#dc2626]', exp.status === 'pending' && 'text-[#999]')} />}
          </div>
          <div className="flex-1">
            <p className="text-[13px] font-medium text-black">
              {exp.status === 'completed' && 'Experiment Completed Successfully'}
              {exp.status === 'running' && 'Experiment Running...'}
              {exp.status === 'failed' && 'Experiment Failed'}
              {exp.status === 'pending' && 'Experiment Pending'}
            </p>
            <p className="text-[11px] text-[#999] mt-0.5">
              {exp.status === 'completed' && exp.updated_at && `Finished ${format(new Date(exp.updated_at), 'PPp')}`}
              {exp.status === 'running' && `Started ${format(new Date(exp.created_at), 'PPp')}`}
              {exp.status === 'failed' && exp.error_message}
              {exp.status === 'pending' && 'Waiting to be launched'}
            </p>
            {exp.status === 'running' && statusData && (
              <div className="flex items-center gap-4 mt-2">
                {statusData.progress && <span className="text-[11px] font-semibold tracking-[0.1em] uppercase text-[#c5a47e] bg-[#faf6f0] px-2 py-0.5">{statusData.progress}</span>}
                {statusData.elapsed_seconds != null && <span className="text-[11px] text-[#999]">Elapsed: {statusData.elapsed_seconds >= 3600 ? `${Math.floor(statusData.elapsed_seconds / 3600)}h ${Math.floor((statusData.elapsed_seconds % 3600) / 60)}m` : statusData.elapsed_seconds >= 60 ? `${Math.floor(statusData.elapsed_seconds / 60)}m ${Math.floor(statusData.elapsed_seconds % 60)}s` : `${Math.floor(statusData.elapsed_seconds)}s`}</span>}
              </div>
            )}
          </div>
        </div>

        {/* Logs */}
        {logsData?.logs && logsData.logs.length > 0 && (
          <div className="bg-[#1a1a1a] border border-[#333] overflow-hidden">
            <button onClick={() => setLogsExpanded(!logsExpanded)} className="w-full flex items-center justify-between px-5 py-3 bg-black hover:bg-[#111] transition-colors">
              <div className="flex items-center gap-2 text-[#999]">
                <Terminal className="w-4 h-4" />
                <span className="text-[11px] font-semibold tracking-[0.1em] uppercase">Experiment Logs</span>
                <span className="text-[10px] text-[#666] ml-2">{logsData.total_lines} lines</span>
                {exp.status === 'running' && <span className="ml-2 flex items-center gap-1"><span className="w-1.5 h-1.5 bg-[#c5a47e] rounded-full animate-pulse" /><span className="text-[10px] text-[#c5a47e]">live</span></span>}
              </div>
              {logsExpanded ? <ChevronUp className="w-4 h-4 text-[#666]" /> : <ChevronDown className="w-4 h-4 text-[#666]" />}
            </button>
            {logsExpanded && (
              <div className="max-h-80 overflow-y-auto p-5 font-mono text-[11px] leading-relaxed">
                {logsData.logs.map((line, i) => (
                  <div key={i} className={clsx('py-0.5', line.includes('[ERROR]') && 'text-[#dc2626]', line.includes('[WARNING]') && 'text-[#c5a47e]', line.includes('[INFO]') && 'text-[#666]', !line.includes('[ERROR]') && !line.includes('[WARNING]') && !line.includes('[INFO]') && 'text-[#555]')}>{line}</div>
                ))}
                <div ref={logsEndRef} />
              </div>
            )}
          </div>
        )}

        {/* Main Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2 space-y-6">
            {/* Quant Config */}
            <div className="bg-white border border-[#e5e5e5] p-6">
              <div className="flex items-center gap-3 mb-5"><Layers className="w-5 h-5 text-black" /><h3 className="font-display text-xl text-black">Quantization Configuration</h3></div>
              {detail.quant_configs.map((qc) => (
                <div key={qc.id} className="p-5 bg-[#fafafa] border border-[#e5e5e5]">
                  <div className="flex items-center justify-between mb-4">
                    <span className="px-3 py-1 bg-black text-white text-[10px] font-semibold tracking-[0.15em] uppercase">{qc.method_name.toUpperCase()}</span>
                    <span className="text-[11px] text-[#999]">{qc.duration_seconds?.toFixed(1)}s</span>
                  </div>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-5">
                    <div><p className="stat-label">Bit Width</p><p className="font-display text-lg text-black mt-1">{qc.bit_width}-bit</p></div>
                    <div><p className="stat-label">Group Size</p><p className="font-display text-lg text-black mt-1">{qc.group_size || 'N/A'}</p></div>
                    <div><p className="stat-label">Per-Channel</p><p className="font-display text-lg text-black mt-1">{qc.per_channel ? 'Yes' : 'No'}</p></div>
                    <div><p className="stat-label">Symmetric</p><p className="font-display text-lg text-black mt-1">{qc.is_symmetric ? 'Yes' : 'No'}</p></div>
                  </div>
                  <div className="mt-4 pt-4 border-t border-[#e5e5e5] flex items-center gap-2 text-[11px]">
                    <Database className="w-4 h-4 text-[#999]" /><span className="text-[#999]">Calibration:</span><span className="text-black">{qc.calib_dataset} ({qc.calib_size} samples)</span>
                  </div>
                </div>
              ))}
              {detail.quant_configs.length === 0 && (
                <div className="p-5 border-l-2 border-l-[#c5a47e] bg-[#faf6f0] border border-[#e5e5e5]">
                  <p className="text-[13px] font-medium text-black">No quantization config stored</p>
                  <p className="text-[11px] text-[#999] mt-1">Please create a new experiment from the <Link to="/experiments/new" className="text-black underline">New Experiment</Link> page.</p>
                </div>
              )}
            </div>
            {/* Metrics */}
            <div className="bg-white border border-[#e5e5e5] p-6">
              <div className="flex items-center gap-3 mb-5"><Gauge className="w-5 h-5 text-[#c5a47e]" /><h3 className="font-display text-xl text-black">Evaluation Metrics</h3></div>
              {detail.metrics.length > 0 ? (
                <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
                  {detail.metrics.map((m) => (
                    <div key={m.id} className="p-5 bg-[#fafafa] border border-[#e5e5e5]">
                      <p className="stat-label">{m.metric_name.replace('_', ' ')}</p>
                      <p className="font-display text-3xl font-medium text-black mt-2">{m.value.toFixed(2)}</p>
                      <p className="text-[10px] text-[#999] mt-1">{m.dataset} / {m.split}</p>
                    </div>
                  ))}
                </div>
              ) : <p className="text-[11px] text-[#999]">No metrics recorded yet.</p>}
            </div>
          </div>
          <div className="space-y-6">
            <div className="bg-white border border-[#e5e5e5] p-6">
              <div className="flex items-center gap-3 mb-5"><Cpu className="w-5 h-5 text-[#666]" /><h3 className="font-display text-xl text-black">Model Info</h3></div>
              <div className="space-y-3 text-[13px]">
                <div className="flex justify-between"><span className="text-[#999]">Model</span><span className="text-black font-mono text-[11px]">{exp.model_name}</span></div>
                <div className="flex justify-between"><span className="text-[#999]">Base Precision</span><span className="text-black">{exp.base_precision}</span></div>
                <div className="flex justify-between"><span className="text-[#999]">Hardware</span><span className="text-black">{exp.gpu_type}</span></div>
                <div className="flex justify-between"><span className="text-[#999]">GPU Count</span><span className="text-black">{exp.gpu_count}</span></div>
              </div>
            </div>
            {detail.hardware_stats.length > 0 && (() => {
              const hw = detail.hardware_stats[0];
              return (
                <div className="bg-white border border-[#e5e5e5] p-6">
                  <div className="flex items-center gap-3 mb-5"><Zap className="w-5 h-5 text-[#c5a47e]" /><h3 className="font-display text-xl text-black">Performance</h3></div>
                  <div className="space-y-4">
                    <div>
                      <p className="stat-label mb-2">Latency</p>
                      <div className="grid grid-cols-3 gap-2 text-center">
                        <div className="p-3 bg-[#fafafa] border border-[#e5e5e5]"><p className="text-[10px] text-[#999] uppercase tracking-wider">P50</p><p className="font-display text-lg text-black mt-0.5">{hw.latency_p50}ms</p></div>
                        <div className="p-3 bg-[#fafafa] border border-[#e5e5e5]"><p className="text-[10px] text-[#999] uppercase tracking-wider">P95</p><p className="font-display text-lg text-black mt-0.5">{hw.latency_p95}ms</p></div>
                        <div className="p-3 bg-[#fafafa] border border-[#e5e5e5]"><p className="text-[10px] text-[#999] uppercase tracking-wider">Mean</p><p className="font-display text-lg text-black mt-0.5">{hw.latency_mean}ms</p></div>
                      </div>
                    </div>
                    <div className="space-y-2 text-[13px]">
                      <div className="flex justify-between"><span className="text-[#999]">Throughput</span><span className="text-[#22c55e] font-medium">{hw.tokens_per_second} tok/s</span></div>
                      <div className="flex justify-between"><span className="text-[#999]">Memory Peak</span><span className="text-black">{hw.memory_peak} GB</span></div>
                      <div className="flex justify-between"><span className="text-[#999]">Model Size</span><span className="text-black">{hw.model_size_mb} MB</span></div>
                    </div>
                  </div>
                </div>
              );
            })()}
            <div className="bg-white border border-[#e5e5e5] p-6">
              <div className="flex items-center gap-3 mb-5"><Fingerprint className="w-5 h-5 text-[#666]" /><h3 className="font-display text-xl text-black">Reproducibility</h3></div>
              <div className="space-y-3 text-[13px]">
                {exp.seed != null && <div className="flex justify-between"><span className="text-[#999]">Seed</span><span className="text-black font-mono">{exp.seed}</span></div>}
                {exp.config_hash && <div className="flex justify-between"><span className="text-[#999]">Config Hash</span><span className="text-black font-mono text-[11px]">{exp.config_hash.slice(0, 12)}...</span></div>}
                {exp.environment_id && <div className="flex justify-between"><span className="text-[#999]">Environment</span><span className="text-black font-mono text-[11px]">snap-{exp.environment_id}</span></div>}
                {exp.wandb_run_id && <div className="flex justify-between"><span className="text-[#999]">W&B Run</span><span className="text-black font-mono text-[11px]">{exp.wandb_run_id}</span></div>}
              </div>
            </div>
            <div className="bg-white border border-[#e5e5e5] p-6">
              <h3 className="font-display text-xl text-black mb-5">Metadata</h3>
              <div className="space-y-3 text-[13px]">
                <div className="flex items-center gap-2"><Clock className="w-4 h-4 text-[#999]" /><span className="text-[#999]">Created</span><span className="ml-auto text-black">{format(new Date(exp.created_at), 'MMM d, yyyy HH:mm')}</span></div>
                {exp.git_branch && <div className="flex items-center gap-2"><GitBranch className="w-4 h-4 text-[#999]" /><span className="text-[#999]">Branch</span><span className="ml-auto text-black font-mono text-[11px]">{exp.git_branch}</span></div>}
                {exp.git_sha && <div className="flex items-center gap-2"><Hash className="w-4 h-4 text-[#999]" /><span className="text-[#999]">Commit</span><span className="ml-auto text-black font-mono text-[11px]">{exp.git_sha.slice(0, 7)}</span></div>}
                {(exp.tags ?? []).length > 0 && (
                  <div className="pt-2">
                    <div className="flex items-center gap-2 mb-2"><Tag className="w-4 h-4 text-[#999]" /><span className="text-[#999]">Tags</span></div>
                    <div className="flex flex-wrap gap-2">{(exp.tags ?? []).map((tag) => <span key={tag} className="px-2 py-1 text-[9px] font-semibold tracking-[0.1em] uppercase bg-[#f5f5f5] text-[#666]">{tag}</span>)}</div>
                  </div>
                )}
              </div>
            </div>
            {exp.notes && (<div className="bg-white border border-[#e5e5e5] p-6"><h3 className="font-display text-xl text-black mb-3">Notes</h3><p className="text-[13px] text-[#333] leading-relaxed">{exp.notes}</p></div>)}
          </div>
        </div>

        {exp.wandb_run_url && (
          <div className="bg-white border border-[#e5e5e5] p-6">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-display text-xl text-black flex items-center gap-2"><Zap className="w-5 h-5 text-[#c5a47e]" /> Weights &amp; Biases Run</h3>
              <a href={exp.wandb_run_url} target="_blank" rel="noopener noreferrer" className="flex items-center gap-1 text-[11px] font-semibold tracking-[0.1em] uppercase text-[#666] hover:text-black transition-colors">Open in W&amp;B <ExternalLink className="w-3.5 h-3.5" /></a>
            </div>
            <div className="overflow-hidden border border-[#e5e5e5]"><iframe src={exp.wandb_run_url + '?embedded=true'} title="W&B Run" className="w-full bg-[#fafafa]" style={{ height: '700px' }} sandbox="allow-scripts allow-same-origin allow-popups allow-popups-to-escape-sandbox" referrerPolicy="no-referrer" /></div>
          </div>
        )}

        {ultimateRunning && (
          <div className="bg-white border-l-2 border-l-[#c5a47e] border border-[#e5e5e5] p-6">
            <div className="flex items-center gap-4">
              <div className="p-4 bg-black"><Brain className="w-7 h-7 text-[#c5a47e] animate-pulse" /></div>
              <div className="flex-1">
                <h3 className="font-display text-xl text-black">Agentic Scientist &mdash; Ultimate Analysis</h3>
                <p className="text-[13px] text-[#666] mt-1">The AI scientist is running a deep analysis. This may take 1&ndash;3 minutes.</p>
                <div className="flex items-center gap-3 mt-3"><div className="spinner-dm" style={{ width: 16, height: 16, borderWidth: 1.5 }} /><span className="text-[10px] font-semibold tracking-[0.15em] uppercase text-[#c5a47e]">Analyzing...</span></div>
              </div>
            </div>
          </div>
        )}

        {ultimateResult && (
          <div className="bg-white border border-[#e5e5e5] overflow-hidden">
            <div className="bg-black px-6 py-5">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3"><Brain className="w-5 h-5 text-[#c5a47e]" /><div><h3 className="font-display text-xl text-white">Ultimate Analysis Report</h3><p className="text-[10px] font-semibold tracking-[0.15em] uppercase text-[#c5a47e] mt-0.5">{ultimateResult.thinking_turns} turns &middot; {ultimateResult.tool_calls_count} tool calls</p></div></div>
                <button onClick={() => { if (ultimateTask) dismissTask(ultimateTask.id); }} className="text-[#666] hover:text-white text-[10px] font-semibold tracking-[0.1em] uppercase transition-colors">Dismiss</button>
              </div>
            </div>
            <div className="p-6 space-y-6">
              {ultimateResult.findings.length > 0 && (
                <div>
                  <div className="flex items-center gap-3 mb-4"><Lightbulb className="w-4 h-4 text-[#c5a47e]" /><p className="stat-label">Key Findings ({ultimateResult.findings.length})</p><div className="gold-accent flex-1 max-w-[40px]" /></div>
                  <div className="space-y-3">
                    {ultimateResult.findings.map((f, i) => (
                      <div key={i} className="bg-[#fafafa] border border-[#e5e5e5] p-5">
                        <div className="flex items-center gap-2 mb-2">
                          <span className="font-display text-lg text-[#c5a47e]">#{i + 1}</span>
                          <span className={clsx('text-[9px] font-semibold tracking-[0.1em] uppercase px-2 py-0.5', f.confidence >= 0.8 ? 'bg-[#f0fdf4] text-[#16a34a]' : f.confidence >= 0.5 ? 'bg-[#fef3c7] text-[#d97706]' : 'bg-[#fef2f2] text-[#dc2626]')}>{(f.confidence * 100).toFixed(0)}%</span>
                          {f.category && <span className="text-[9px] font-semibold tracking-[0.1em] uppercase px-2 py-0.5 bg-[#f5f5f5] text-[#666]">{f.category}</span>}
                        </div>
                        <h5 className="font-display text-base text-black">{f.title}</h5>
                        <p className="text-[13px] text-[#666] mt-1 leading-relaxed">{f.description}</p>
                        {f.evidence && <div className="mt-3 p-3 bg-white border border-[#e5e5e5] text-[11px] font-mono text-[#666]">{f.evidence}</div>}
                      </div>
                    ))}
                  </div>
                </div>
              )}
              {ultimateResult.follow_up_experiments.length > 0 && (
                <div>
                  <div className="flex items-center gap-3 mb-4"><FlaskConical className="w-4 h-4 text-[#666]" /><p className="stat-label">Suggested Follow-ups</p><div className="flex-1 h-px bg-[#e5e5e5]" /></div>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    {ultimateResult.follow_up_experiments.map((fe, i) => (
                      <div key={i} className="border-l-2 border-l-[#c5a47e] bg-[#fafafa] border border-[#e5e5e5] p-4">
                        <span className={clsx('text-[9px] font-semibold tracking-[0.1em] uppercase px-1.5 py-0.5', fe.priority >= 7 ? 'bg-[#fef2f2] text-[#dc2626]' : fe.priority >= 4 ? 'bg-[#fef3c7] text-[#d97706]' : 'bg-[#f5f5f5] text-[#666]')}>P{fe.priority}</span>
                        <p className="text-[13px] text-black font-medium mt-1.5">{fe.description}</p>
                        <p className="text-[11px] text-[#999] mt-1">{fe.rationale}</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}
              {ultimateResult.raw_reasoning && (
                <div>
                  <div className="flex items-center gap-3 mb-4"><BarChart3 className="w-4 h-4 text-[#666]" /><p className="stat-label">Full Analysis</p><div className="flex-1 h-px bg-[#e5e5e5]" /></div>
                  <div className="bg-[#fafafa] border border-[#e5e5e5] p-6 max-h-[500px] overflow-y-auto prose-luxury">
                    <div className="text-[#333] whitespace-pre-wrap text-[13px] leading-relaxed" dangerouslySetInnerHTML={{ __html: ultimateResult.raw_reasoning.replace(/^## (.+)$/gm, '<h3>$1</h3>').replace(/^### (.+)$/gm, '<h4>$1</h4>').replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>').replace(/`(.+?)`/g, '<code>$1</code>') }} />
                  </div>
                </div>
              )}
              <div className="flex items-center gap-6 pt-4 border-t border-[#e5e5e5] text-[10px] font-semibold tracking-[0.1em] uppercase text-[#999]">
                <span>{ultimateResult.thinking_turns} turns</span><span>{ultimateResult.tool_calls_count} tool calls</span><span>{ultimateResult.findings.length} findings</span>
                {ultimateResult.plots.length > 0 && <span>{ultimateResult.plots.length} plots</span>}
              </div>
            </div>
          </div>
        )}

        {detail.scientist_reports.length > 0 && (
          <div className="bg-white border border-[#e5e5e5] p-6">
            <div className="flex items-center justify-between mb-5">
              <div className="flex items-center gap-3"><FileText className="w-5 h-5 text-[#c5a47e]" /><h3 className="font-display text-xl text-black">AI Analysis Report</h3></div>
              <div className="flex items-center gap-2">
                <span className={clsx('px-3 py-1 text-[10px] font-semibold tracking-[0.1em] uppercase', detail.scientist_reports[0].pass_fail === 'pass' && 'bg-[#f0fdf4] text-[#16a34a]', detail.scientist_reports[0].pass_fail === 'fail' && 'bg-[#fef2f2] text-[#dc2626]')}>{detail.scientist_reports[0].pass_fail?.toUpperCase()}</span>
                <span className="text-[11px] text-[#999]">Confidence: {((detail.scientist_reports[0].confidence_score || 0) * 100).toFixed(0)}%</span>
              </div>
            </div>
            <div className="prose-luxury">
              <div className="text-[#333] whitespace-pre-wrap" dangerouslySetInnerHTML={{ __html: detail.scientist_reports[0].report_markdown.replace(/^## (.+)$/gm, '<h3>$1</h3>').replace(/^### (.+)$/gm, '<h4>$1</h4>').replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>').replace(/`(.+?)`/g, '<code>$1</code>') }} />
            </div>
            {detail.scientist_reports[0].key_findings?.length > 0 && (
              <div className="mt-6 pt-6 border-t border-[#e5e5e5]"><p className="stat-label mb-3">Key Findings</p><div className="flex flex-wrap gap-2">{detail.scientist_reports[0].key_findings.map((f: string, i: number) => <span key={i} className="px-3 py-1.5 bg-[#faf6f0] text-[#333] text-[11px] border border-[#e5e5e5]">{f}</span>)}</div></div>
            )}
            {detail.scientist_reports[0].suggested_experiments?.length > 0 && (
              <div className="mt-4"><p className="stat-label mb-3">Suggested Next Steps</p><div className="space-y-2">{detail.scientist_reports[0].suggested_experiments.map((s: string, i: number) => <div key={i} className="flex items-center gap-3 p-3 bg-[#fafafa] border border-[#e5e5e5]"><Play className="w-4 h-4 text-[#c5a47e]" /><span className="text-[13px] text-[#333]">{s}</span></div>)}</div></div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
