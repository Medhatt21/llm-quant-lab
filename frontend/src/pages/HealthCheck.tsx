import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Cpu,
  Database,
  Brain,
  BarChart3,
  Server,
  Container,
  HardDrive,
  RefreshCw,
  Wifi,
  WifiOff,
  Gauge,
  Wrench,
  ChevronDown,
  ChevronRight,
} from 'lucide-react';
import clsx from 'clsx';
import Header from '../components/Layout/Header';
import LoadingState from '../components/LoadingState';
import { healthCheckFull } from '../api/client';

const STATUS_CONFIG: Record<string, { icon: typeof CheckCircle2; color: string; bg: string; label: string }> = {
  healthy: { icon: CheckCircle2, color: 'text-[#2D8A4E]', bg: 'bg-[#fafafa] border-[#2D8A4E]/20', label: 'Healthy' },
  degraded: { icon: AlertTriangle, color: 'text-[#C5A47E]', bg: 'bg-[#fafafa] border-[#C5A47E]/30', label: 'Degraded' },
  unhealthy: { icon: XCircle, color: 'text-[#C53030]', bg: 'bg-[#fafafa] border-[#C53030]/20', label: 'Unhealthy' },
  error: { icon: XCircle, color: 'text-[#C53030]', bg: 'bg-[#fafafa] border-[#C53030]/20', label: 'Error' },
  unavailable: { icon: WifiOff, color: 'text-[#999]', bg: 'bg-[#fafafa] border-[#e5e5e5]', label: 'Unavailable' },
  not_configured: { icon: AlertTriangle, color: 'text-[#C5A47E]', bg: 'bg-[#fafafa] border-[#C5A47E]/30', label: 'Not Configured' },
  unreachable: { icon: WifiOff, color: 'text-[#C53030]', bg: 'bg-[#fafafa] border-[#C53030]/20', label: 'Unreachable' },
};

function getStatusConfig(status: string) {
  return STATUS_CONFIG[status] || STATUS_CONFIG.unavailable;
}

export default function HealthCheck() {
  const { data, isLoading, isError, error, refetch, isFetching, dataUpdatedAt } = useQuery({
    queryKey: ['health-full'],
    queryFn: healthCheckFull,
    refetchInterval: 30_000,
    retry: 1,
    staleTime: 10_000,
  });

  if (isLoading) {
    return (
      <div className="min-h-screen">
        <Header title="System Health" subtitle="Checking all subsystems..." />
        <LoadingState message="Running health checks..." />
      </div>
    );
  }

  if (isError || !data) {
    return (
      <div className="min-h-screen">
        <Header title="System Health" subtitle="Health check failed" />
        <div className="p-6">
          <div className="bg-[#fafafa] border border-[#C53030]/20 p-6 text-center">
            <XCircle className="w-12 h-12 text-[#C53030] mx-auto mb-3" />
            <h2 className="text-lg font-display font-semibold text-black mb-2">Cannot Reach API</h2>
            <p className="text-sm text-[#666] mb-4">
              {error instanceof Error ? error.message : 'Failed to connect to the backend API server.'}
            </p>
            <button
              onClick={() => refetch()}
              className="px-4 py-2 bg-black hover:bg-[#333] text-white text-sm font-medium tracking-wide uppercase transition-colors"
            >
              Retry
            </button>
          </div>
        </div>
      </div>
    );
  }

  const checks = data.checks;
  const overallStatus = getStatusConfig(data.status);
  const OverallIcon = overallStatus.icon;

  return (
    <div className="min-h-screen">
      <Header title="System Health" subtitle="Monitor all subsystems and services" />

      <div className="p-6 max-w-6xl mx-auto space-y-6">
        {/* Overall Status Banner */}
        <div className={clsx('flex items-center justify-between p-5 border', overallStatus.bg)}>
          <div className="flex items-center gap-4">
            <div className={clsx('p-3', data.status === 'healthy' ? 'bg-[#2D8A4E]/10' : 'bg-[#C5A47E]/10')}>
              <OverallIcon className={clsx('w-7 h-7', overallStatus.color)} />
            </div>
            <div>
              <h2 className="text-lg font-display font-bold text-black">
                System {overallStatus.label}
              </h2>
              <p className="text-sm text-[#999]">
                v{data.version} &middot; Last checked {dataUpdatedAt ? new Date(dataUpdatedAt).toLocaleTimeString() : 'just now'}
              </p>
            </div>
          </div>
          <button
            onClick={() => refetch()}
            disabled={isFetching}
            className="flex items-center gap-2 px-4 py-2 bg-white border border-[#e5e5e5] text-sm text-[#666] hover:text-black hover:border-[#999] transition-colors disabled:opacity-50"
          >
            <RefreshCw className={clsx('w-4 h-4', isFetching && 'animate-spin')} />
            {isFetching ? 'Checking...' : 'Refresh'}
          </button>
        </div>

        {/* Health Check Cards Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          <HealthCard
            title="GPU"
            icon={<Cpu className="w-5 h-5" />}
            check={checks.gpu}
            details={checks.gpu?.status === 'healthy' ? [
              { label: 'Device', value: checks.gpu.gpu_name as string },
              { label: 'Count', value: `x${checks.gpu.gpu_count}` },
              { label: 'VRAM Total', value: `${checks.gpu.memory_total_gb} GB` },
              { label: 'VRAM Allocated', value: `${checks.gpu.memory_allocated_gb} GB` },
              { label: 'VRAM Reserved', value: `${checks.gpu.memory_reserved_gb} GB` },
            ] : undefined}
          />

          <HealthCard
            title="LLM Provider"
            icon={<Wifi className="w-5 h-5" />}
            check={checks.llm}
            details={checks.llm ? [
              { label: 'Provider', value: (checks.llm.provider as string) || 'N/A' },
              { label: 'Model', value: (checks.llm.model as string) || 'N/A' },
              { label: 'Base URL', value: (checks.llm.base_url as string) || 'N/A' },
            ] : undefined}
          />

          <ScientistToolsCard check={checks.scientist} />

          <HealthCard
            title="Analytics Engine"
            icon={<BarChart3 className="w-5 h-5" />}
            check={checks.analytics}
          />

          <HealthCard
            title="Database"
            icon={<Database className="w-5 h-5" />}
            check={checks.database}
            details={checks.database?.status === 'healthy' ? [
              { label: 'Experiments', value: String(checks.database.experiment_count || 0) },
              { label: 'Engine', value: 'PostgreSQL 16' },
            ] : undefined}
          />

          <HealthCard
            title="System Resources"
            icon={<HardDrive className="w-5 h-5" />}
            check={checks.system}
            details={checks.system ? [
              { label: 'Disk Total', value: `${checks.system.disk_total_gb} GB` },
              { label: 'Disk Used', value: `${checks.system.disk_used_gb} GB` },
              { label: 'Disk Free', value: `${checks.system.disk_free_gb} GB` },
            ] : undefined}
            customContent={checks.system && (
              <DiskUsageBar
                used={checks.system.disk_used_gb as number}
                total={checks.system.disk_total_gb as number}
              />
            )}
          />
        </div>

        {/* Containers Section */}
        <ContainersSection check={checks.containers} />

        {/* Quick Diagnostics */}
        <div className="bg-white border-0 border border-[#e5e5e5] p-5">
          <h3 className="font-display font-semibold text-black mb-4 flex items-center gap-2">
            <Gauge className="w-5 h-5 text-black" />
            Quick Diagnostics
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <DiagnosticItem
              label="API Server"
              status="healthy"
              detail={`v${data.version}`}
            />
            <DiagnosticItem
              label="GPU Compute"
              status={checks.gpu?.status || 'unavailable'}
              detail={checks.gpu?.message || 'N/A'}
            />
            <DiagnosticItem
              label="LLM Inference"
              status={checks.llm?.status || 'not_configured'}
              detail={checks.llm?.message || 'N/A'}
            />
            <DiagnosticItem
              label="Database"
              status={checks.database?.status || 'unhealthy'}
              detail={checks.database?.message || 'N/A'}
            />
            <DiagnosticItem
              label="Scientist Pipeline"
              status={checks.scientist?.status || 'unhealthy'}
              detail={checks.scientist?.message || 'N/A'}
            />
            <DiagnosticItem
              label="Analytics"
              status={checks.analytics?.status || 'unhealthy'}
              detail={checks.analytics?.message || 'N/A'}
            />
          </div>
        </div>
      </div>
    </div>
  );
}

interface HealthCardProps {
  title: string;
  icon: React.ReactNode;
  check?: { status: string; message: string; [key: string]: unknown };
  details?: Array<{ label: string; value: string }>;
  customContent?: React.ReactNode;
}

function HealthCard({ title, icon, check, details, customContent }: HealthCardProps) {
  if (!check) {
    return (
      <div className="bg-white border-0 border border-[#e5e5e5] p-5">
        <div className="flex items-center gap-3 mb-3">
          <div className="p-2 rounded-none bg-[#f5f5f5] text-[#999]">{icon}</div>
          <h3 className="font-display font-semibold text-black">{title}</h3>
        </div>
        <p className="text-sm text-[#999]">No data available</p>
      </div>
    );
  }

  const config = getStatusConfig(check.status);
  const StatusIcon = config.icon;

  return (
    <div className={clsx('border-0 border p-5', config.bg)}>
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-3">
          <div className={clsx(
            'p-2 rounded-none',
            check.status === 'healthy' ? 'bg-[#2D8A4E]/10 text-[#2D8A4E]' :
            check.status === 'degraded' ? 'bg-[#C5A47E]/10 text-[#C5A47E]' :
            check.status === 'unhealthy' || check.status === 'error' ? 'bg-[#C53030]/10 text-[#C53030]' :
            'bg-[#f5f5f5] text-[#999]'
          )}>
            {icon}
          </div>
          <h3 className="font-display font-semibold text-black">{title}</h3>
        </div>
        <div className="flex items-center gap-1.5">
          <StatusIcon className={clsx('w-4 h-4', config.color)} />
          <span className={clsx('text-xs font-medium', config.color)}>{config.label}</span>
        </div>
      </div>

      <p className="text-sm text-[#666] mb-3">{check.message}</p>

      {details && (
        <div className="space-y-1.5">
          {details.map((d) => (
            <div key={d.label} className="flex justify-between text-xs">
              <span className="text-[#999]">{d.label}</span>
              <span className="text-black font-medium font-mono truncate ml-2 max-w-[200px]">{d.value}</span>
            </div>
          ))}
        </div>
      )}

      {customContent}
    </div>
  );
}

function DiskUsageBar({ used, total }: { used: number; total: number }) {
  const pct = total > 0 ? Math.round((used / total) * 100) : 0;
  const color = pct > 90 ? 'bg-[#C53030]' : pct > 75 ? 'bg-[#C5A47E]' : 'bg-[#2D8A4E]';

  return (
    <div className="mt-3">
      <div className="flex justify-between text-xs text-[#999] mb-1">
        <span>Disk Usage</span>
        <span>{pct}%</span>
      </div>
      <div className="h-2 bg-[#e5e5e5] overflow-hidden">
        <div className={clsx('h-full transition-all', color)} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

function ContainersSection({ check }: { check?: { status: string; message: string; containers?: Array<{ name: string; status: string; ports: string }> } }) {
  if (!check) return null;

  const containers = (check as any).containers as Array<{ name: string; status: string; ports: string }> | undefined;

  return (
    <div className="bg-white border-0 border border-[#e5e5e5] p-5">
      <h3 className="font-display font-semibold text-black mb-4 flex items-center gap-2">
        <Container className="w-5 h-5 text-black" />
        Containers
        <span className="text-xs text-[#999] font-normal ml-2">{check.message}</span>
      </h3>

      {containers && containers.length > 0 ? (
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-[#e5e5e5]">
                <th className="px-4 py-2 text-left text-xs font-medium text-[#999] uppercase">Name</th>
                <th className="px-4 py-2 text-left text-xs font-medium text-[#999] uppercase">Status</th>
                <th className="px-4 py-2 text-left text-xs font-medium text-[#999] uppercase">Ports</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#e5e5e5]">
              {containers.map((c, i) => {
                const isUp = c.status.toLowerCase().includes('up');
                return (
                  <tr key={i} className="hover:bg-[#fafafa]">
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <div className={clsx('w-2 h-2 rounded-full', isUp ? 'bg-[#2D8A4E]' : 'bg-[#C53030]')} />
                        <span className="text-sm font-medium text-black font-mono">{c.name}</span>
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <span className={clsx('text-sm', isUp ? 'text-[#2D8A4E]' : 'text-[#C53030]')}>{c.status}</span>
                    </td>
                    <td className="px-4 py-3 text-sm text-[#999] font-mono text-xs">{c.ports || '\u2014'}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="text-center py-6">
          <Server className="w-8 h-8 text-[#ccc] mx-auto mb-2" />
          <p className="text-sm text-[#999]">{check.message}</p>
        </div>
      )}
    </div>
  );
}

interface ScientistTool {
  name: string;
  status: string;
  message: string;
  description: string;
  params: string[];
}

const TOOL_ICONS: Record<string, string> = {
  query_experiments: '🗄️',
  query_wandb: '📊',
  execute_analysis_code: '🐍',
  generate_plot: '📈',
  search_arxiv: '📚',
  compute_statistics: '📐',
  read_file: '📖',
  generate_latex_table: '📋',
  inspect_model_weights: '🔬',
  query_knowledge_graph: '🕸️',
  compare_experiments: '🔀',
  compute_pareto_frontier: '⚡',
  web_search: '🌐',
};

function ScientistToolsCard({ check }: { check?: { status: string; message: string; [key: string]: unknown } }) {
  const [expanded, setExpanded] = useState(false);

  if (!check) {
    return (
      <div className="bg-white border-0 border border-[#e5e5e5] p-5">
        <div className="flex items-center gap-3 mb-3">
          <div className="p-2 rounded-none bg-[#f5f5f5] text-[#999]"><Brain className="w-5 h-5" /></div>
          <h3 className="font-display font-semibold text-black">Scientist Tools</h3>
        </div>
        <p className="text-sm text-[#999]">No data available</p>
      </div>
    );
  }

  const config = getStatusConfig(check.status);
  const StatusIcon = config.icon;
  const tools = (check.tools as ScientistTool[] | undefined) || [];
  const healthyCount = check.tools_healthy as number | undefined;
  const totalCount = check.tools_count as number | undefined;

  return (
    <div className={clsx('border-0 border p-5', config.bg)}>
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-3">
          <div className={clsx(
            'p-2 rounded-none',
            check.status === 'healthy' ? 'bg-[#2D8A4E]/10 text-[#2D8A4E]' :
            check.status === 'degraded' ? 'bg-[#C5A47E]/10 text-[#C5A47E]' :
            'bg-[#C53030]/10 text-[#C53030]'
          )}>
            <Brain className="w-5 h-5" />
          </div>
          <h3 className="font-display font-semibold text-black">Scientist Tools</h3>
        </div>
        <div className="flex items-center gap-1.5">
          <StatusIcon className={clsx('w-4 h-4', config.color)} />
          <span className={clsx('text-xs font-medium', config.color)}>{config.label}</span>
        </div>
      </div>

      <p className="text-sm text-[#666] mb-3">{check.message}</p>

      {/* Summary bar */}
      {healthyCount !== undefined && totalCount !== undefined && totalCount > 0 && (
        <div className="mb-3">
          <div className="flex justify-between text-xs text-[#999] mb-1">
            <span>Tool Health</span>
            <span>{healthyCount}/{totalCount} operational</span>
          </div>
          <div className="h-2 bg-[#e5e5e5] overflow-hidden">
            <div
              className={clsx(
                'h-full transition-all',
                healthyCount === totalCount ? 'bg-[#2D8A4E]' : healthyCount >= totalCount * 0.8 ? 'bg-[#C5A47E]' : 'bg-[#C53030]'
              )}
              style={{ width: `${Math.round((healthyCount / totalCount) * 100)}%` }}
            />
          </div>
        </div>
      )}

      {/* Expand/collapse for tool list */}
      {tools.length > 0 && (
        <>
          <button
            onClick={() => setExpanded(!expanded)}
            className="flex items-center gap-2 text-xs text-[#999] hover:text-black transition-colors mt-1 mb-2"
          >
            {expanded ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
            <Wrench className="w-3.5 h-3.5" />
            <span>{expanded ? 'Hide' : 'Show'} individual tools</span>
          </button>

          {expanded && (
            <div className="space-y-1.5 mt-2 max-h-80 overflow-y-auto">
              {tools.map((tool) => {
                const toolConfig = getStatusConfig(tool.status);
                const ToolStatusIcon = toolConfig.icon;
                return (
                  <div
                    key={tool.name}
                    className="flex items-center gap-2.5 p-2 rounded-none bg-white/60 border border-[#f0f0f0]"
                  >
                    <span className="text-base flex-shrink-0 w-6 text-center">{TOOL_ICONS[tool.name] || '🔧'}</span>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-medium text-black font-mono">{tool.name}</span>
                        <ToolStatusIcon className={clsx('w-3 h-3', toolConfig.color)} />
                      </div>
                      <p className="text-[10px] text-[#999] truncate" title={tool.description}>
                        {tool.message}
                      </p>
                    </div>
                    <div className="flex-shrink-0">
                      <span className={clsx(
                        'text-[10px] px-1.5 py-0.5 rounded-full font-medium',
                        tool.status === 'healthy' ? 'bg-[#2D8A4E]/10 text-[#2D8A4E]' :
                        tool.status === 'degraded' ? 'bg-[#C5A47E]/10 text-[#C5A47E]' :
                        'bg-[#C53030]/10 text-[#C53030]'
                      )}>
                        {tool.status}
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </>
      )}
    </div>
  );
}

function DiagnosticItem({ label, status, detail }: { label: string; status: string; detail: string }) {
  const config = getStatusConfig(status);
  const Icon = config.icon;

  return (
    <div className="flex items-center justify-between p-3 bg-[#fafafa] rounded-none">
      <div className="flex items-center gap-3">
        <Icon className={clsx('w-4 h-4', config.color)} />
        <span className="text-sm font-medium text-black">{label}</span>
      </div>
      <span className="text-xs text-[#999] truncate ml-4 max-w-[250px]">{detail}</span>
    </div>
  );
}
