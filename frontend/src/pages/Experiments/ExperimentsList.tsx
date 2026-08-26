import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { 
  Search, 
  Filter, 
  Plus, 
  CheckCircle2, 
  XCircle, 
  Clock, 
  Loader2,
  ChevronDown,
  MoreVertical,
  Eye,
  Trash2,
  Copy,
  FileText,
  ExternalLink
} from 'lucide-react';
import clsx from 'clsx';
import { formatDistanceToNow, format } from 'date-fns';
import Header from '../../components/Layout/Header';
import APIError from '../../components/APIError';
import LoadingState from '../../components/LoadingState';
import { getExperiments, deleteExperiment } from '../../api/client';
import type { Experiment } from '../../types';

const statusConfig: Record<string, {
  icon: typeof CheckCircle2;
  color: string;
  bg: string;
  label: string;
  animate?: boolean;
}> = {
  completed: { icon: CheckCircle2, color: 'text-[#22c55e]', bg: 'bg-[#f0fdf4]', label: 'Completed' },
  running: { icon: Loader2, color: 'text-[#c5a47e]', bg: 'bg-[#faf6f0]', label: 'Running', animate: true },
  failed: { icon: XCircle, color: 'text-[#dc2626]', bg: 'bg-[#fef2f2]', label: 'Failed' },
  pending: { icon: Clock, color: 'text-[#999]', bg: 'bg-[#f5f5f5]', label: 'Pending' },
  cancelled: { icon: XCircle, color: 'text-[#999]', bg: 'bg-[#f5f5f5]', label: 'Cancelled' },
};

export default function ExperimentsList() {
  const queryClient = useQueryClient();
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter] = useState<string | null>(null);
  const [selectedExperiments, setSelectedExperiments] = useState<number[]>([]);

  const { data: apiData, isLoading, isError, error, refetch } = useQuery({
    queryKey: ['experiments', statusFilter],
    queryFn: () => getExperiments({ limit: 100, status: statusFilter || undefined }),
    retry: 2,
    staleTime: 30_000,
  });

  const deleteMutation = useMutation({
    mutationFn: async (ids: number[]) => {
      for (const id of ids) {
        await deleteExperiment(id);
      }
    },
    onSuccess: () => {
      setSelectedExperiments([]);
      queryClient.invalidateQueries({ queryKey: ['experiments'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard-stats'] });
    },
    onError: (err) => {
      alert(`Delete failed: ${err instanceof Error ? err.message : err}`);
    },
  });

  if (isLoading) {
    return (
      <div className="min-h-screen">
        <Header title="Experiments" subtitle="Loading..." />
        <LoadingState message="Loading experiments..." />
      </div>
    );
  }

  if (isError || !apiData) {
    return (
      <div className="min-h-screen">
        <Header title="Experiments" subtitle="Error" />
        <APIError
          title="Could not load experiments"
          error={error}
          onRetry={() => refetch()}
        />
      </div>
    );
  }

  const experiments = apiData.experiments;

  const filteredExperiments = experiments.filter((exp) => {
    const matchesSearch = 
      exp.name?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      exp.model_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (exp.tags ?? []).some(tag => tag.toLowerCase().includes(searchQuery.toLowerCase()));
    const matchesStatus = !statusFilter || exp.status === statusFilter;
    return matchesSearch && matchesStatus;
  });

  const toggleSelect = (id: number) => {
    setSelectedExperiments(prev => 
      prev.includes(id) ? prev.filter(i => i !== id) : [...prev, id]
    );
  };

  const toggleSelectAll = () => {
    if (selectedExperiments.length === filteredExperiments.length) {
      setSelectedExperiments([]);
    } else {
      setSelectedExperiments(filteredExperiments.map(e => e.id));
    }
  };

  return (
    <div className="min-h-screen">
      <Header 
        title="Experiments" 
        subtitle={`${filteredExperiments.length} experiments`}
      />

      <div className="p-6">
        {/* Toolbar */}
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-4">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#999]" />
              <input
                type="text"
                placeholder="Search experiments..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-80 pl-10 pr-4 py-2.5 bg-white border border-[#e5e5e5] text-[13px] text-[#333] placeholder-[#999] focus:outline-none focus:border-black transition-colors"
              />
            </div>
            <div className="relative">
              <button className="flex items-center gap-2 px-4 py-2.5 bg-white border border-[#e5e5e5] text-[11px] font-semibold tracking-[0.1em] uppercase text-[#666] hover:text-black hover:border-[#999] transition-colors">
                <Filter className="w-4 h-4" />
                {statusFilter ? statusConfig[statusFilter]?.label : 'All Status'}
                <ChevronDown className="w-4 h-4" />
              </button>
            </div>
          </div>
          <Link
            to="/experiments/new"
            className="flex items-center gap-2 px-5 py-2.5 bg-black hover:bg-[#1a1a1a] text-white text-[11px] font-semibold tracking-[0.15em] uppercase transition-colors"
          >
            <Plus className="w-4 h-4" />
            New Experiment
          </Link>
        </div>

        {/* Bulk Actions */}
        {selectedExperiments.length > 0 && (
          <div className="flex items-center gap-4 mb-4 p-3 bg-white border border-[#e5e5e5] rounded-none">
            <span className="text-sm text-[#666]">{selectedExperiments.length} selected</span>
            <div className="flex items-center gap-2">
              <button className="px-3 py-1.5 text-sm text-[#666] hover:text-black hover:bg-[#f5f5f5] rounded-none transition-colors">Compare</button>
              <button className="px-3 py-1.5 text-sm text-[#666] hover:text-black hover:bg-[#f5f5f5] rounded-none transition-colors">Export</button>
              <button
                onClick={() => { if (confirm(`Delete ${selectedExperiments.length} experiment(s)?`)) deleteMutation.mutate(selectedExperiments); }}
                disabled={deleteMutation.isPending}
                className="px-3 py-1.5 text-sm text-red-500 hover:text-red-700 hover:bg-red-50 rounded-none transition-colors"
              >{deleteMutation.isPending ? 'Deleting...' : 'Delete'}</button>
            </div>
          </div>
        )}

        {/* Table */}
        <div className="bg-white border border-[#e5e5e5] overflow-hidden">
          <table className="table-dm">
            <thead>
              <tr>
                <th className="w-12">
                  <input type="checkbox" checked={selectedExperiments.length === filteredExperiments.length && filteredExperiments.length > 0} onChange={toggleSelectAll} className="w-4 h-4 border-[#666] bg-white" />
                </th>
                <th>Experiment</th>
                <th>Model</th>
                <th>Status</th>
                <th>Hardware</th>
                <th>Created</th>
                <th className="w-12"></th>
              </tr>
            </thead>
            <tbody>
              {filteredExperiments.map((exp) => (
                <ExperimentRow key={exp.id} experiment={exp} isSelected={selectedExperiments.includes(exp.id)} onToggleSelect={() => toggleSelect(exp.id)} onDelete={(id) => { if (confirm(`Delete experiment #${id}?`)) deleteMutation.mutate([id]); }} />
              ))}
            </tbody>
          </table>
          {filteredExperiments.length === 0 && (
            <div className="px-6 py-12 text-center">
              <p className="text-gray-500">No experiments found. Run your first experiment to get started.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

interface ExperimentRowProps {
  experiment: Experiment;
  isSelected: boolean;
  onToggleSelect: () => void;
  onDelete: (id: number) => void;
}

function ExperimentRow({ experiment, isSelected, onToggleSelect, onDelete }: ExperimentRowProps) {
  const [showMenu, setShowMenu] = useState(false);
  const status = statusConfig[experiment.status] || statusConfig.pending;
  const StatusIcon = status.icon;

  return (
    <tr className="hover:bg-[#fafafa] transition-colors group">
      <td className="px-4 py-4">
        <input type="checkbox" checked={isSelected} onChange={onToggleSelect} className="w-4 h-4 rounded border-[#e5e5e5] bg-white text-black focus:ring-black/20" />
      </td>
      <td className="px-4 py-4">
        <Link to={`/experiments/${experiment.id}`} className="block">
          <div className="flex items-center gap-3">
            <div className={clsx('p-2', status.bg)}>
              <StatusIcon className={clsx('w-4 h-4', status.color, status.animate && 'animate-spin')} />
            </div>
              <div>
              <p className="font-medium text-black hover:text-[#c5a47e] transition-colors">
                <span className="text-[#999] font-mono text-[11px] mr-1.5">#{experiment.id}</span>
                {experiment.name || `Experiment #${experiment.id}`}
              </p>
              <div className="flex items-center gap-2 mt-1">
                {(experiment.tags ?? []).slice(0, 3).map((tag) => (
                  <span key={tag} className="px-1.5 py-0.5 text-[9px] font-semibold tracking-[0.1em] uppercase bg-[#f5f5f5] text-[#666]">{tag}</span>
                ))}
                {experiment.wandb_run_url && (
                  <a
                    href={experiment.wandb_run_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    onClick={(e) => e.stopPropagation()}
                    className="inline-flex items-center gap-1 px-1.5 py-0.5 text-xs bg-[#C5A47E]/10 text-[#C5A47E] rounded hover:bg-[#C5A47E]/20 transition-colors"
                    title="Open in W&B"
                  >
                    W&B <ExternalLink className="w-3 h-3" />
                  </a>
                )}
              </div>
            </div>
          </div>
        </Link>
      </td>
      <td className="px-4 py-4">
        <p className="text-[13px] text-black font-mono">{experiment.model_name}</p>
        <p className="text-[11px] text-[#999] mt-0.5">{experiment.base_precision}</p>
      </td>
      <td className="px-4 py-4">
        <span className={clsx('inline-flex items-center gap-1.5 px-2.5 py-1 text-[9px] font-semibold tracking-[0.1em] uppercase', status.bg, status.color)}>{status.label}</span>
      </td>
      <td className="px-4 py-4">
        <p className="text-[13px] text-[#333]">{experiment.gpu_type || 'N/A'}</p>
        <p className="text-[11px] text-[#999] mt-0.5">x{experiment.gpu_count}</p>
      </td>
      <td className="px-4 py-4">
        <p className="text-[13px] text-[#333]">{formatDistanceToNow(new Date(experiment.created_at), { addSuffix: true })}</p>
        <p className="text-[11px] text-[#999] mt-0.5">{format(new Date(experiment.created_at), 'MMM d, HH:mm')}</p>
      </td>
      <td className="px-4 py-4">
        <div className="relative">
          <button onClick={() => setShowMenu(!showMenu)} className="p-1.5 text-[#999] hover:text-black hover:bg-[#f5f5f5] opacity-0 group-hover:opacity-100 transition-all">
            <MoreVertical className="w-4 h-4" />
          </button>
          {showMenu && (
            <div className="absolute right-0 mt-1 w-48 bg-white border border-[#e5e5e5] shadow-[0_2px_20px_rgba(0,0,0,0.1)] z-10">
              <div className="py-1">
                <Link to={`/experiments/${experiment.id}`} className="flex items-center gap-2 px-4 py-2 text-[11px] text-[#666] hover:text-black hover:bg-[#f5f5f5]">
                  <Eye className="w-4 h-4" /> View Details
                </Link>
                <button className="w-full flex items-center gap-2 px-4 py-2 text-[11px] text-[#666] hover:text-black hover:bg-[#f5f5f5]">
                  <Copy className="w-4 h-4" /> Duplicate
                </button>
                <button className="w-full flex items-center gap-2 px-4 py-2 text-[11px] text-[#666] hover:text-black hover:bg-[#f5f5f5]">
                  <FileText className="w-4 h-4" /> Generate Report
                </button>
                <hr className="my-1 border-[#e5e5e5]" />
                <button onClick={() => { setShowMenu(false); onDelete(experiment.id); }} className="w-full flex items-center gap-2 px-4 py-2 text-[11px] text-[#dc2626] hover:bg-[#fef2f2]">
                  <Trash2 className="w-4 h-4" /> Delete
                </button>
              </div>
            </div>
          )}
        </div>
      </td>
    </tr>
  );
}
