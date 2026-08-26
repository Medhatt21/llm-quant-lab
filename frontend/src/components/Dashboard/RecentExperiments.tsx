import { Link } from 'react-router-dom';
import {
  ArrowRight,
  CheckCircle2,
  XCircle,
  Clock,
  Loader2,
} from 'lucide-react';
import clsx from 'clsx';
import { formatDistanceToNow } from 'date-fns';
import type { Experiment } from '../../types';

interface RecentExperimentsProps {
  experiments: Experiment[];
}

const statusConfig: Record<string, {
  icon: typeof CheckCircle2;
  color: string;
  label: string;
  animate?: boolean;
}> = {
  completed: { icon: CheckCircle2, color: 'text-[#22c55e]', label: 'Completed' },
  running: { icon: Loader2, color: 'text-[#c5a47e]', label: 'Running', animate: true },
  failed: { icon: XCircle, color: 'text-[#dc2626]', label: 'Failed' },
  pending: { icon: Clock, color: 'text-[#999]', label: 'Pending' },
  cancelled: { icon: XCircle, color: 'text-[#999]', label: 'Cancelled' },
};

export default function RecentExperiments({ experiments }: RecentExperimentsProps) {
  return (
    <div className="bg-white border border-[#e5e5e5] overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-6 py-4 border-b border-[#e5e5e5]">
        <h3 className="font-display text-xl text-black">Recent Experiments</h3>
        <Link
          to="/experiments"
          className="flex items-center gap-1 text-[11px] font-semibold tracking-[0.1em] uppercase text-[#666] hover:text-black transition-colors"
        >
          View all
          <ArrowRight className="w-3.5 h-3.5" />
        </Link>
      </div>

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="table-dm">
          <thead>
            <tr>
              <th>Experiment</th>
              <th>Model</th>
              <th>Status</th>
              <th className="text-right">Time</th>
            </tr>
          </thead>
          <tbody>
            {experiments.map((exp) => {
              const status = statusConfig[exp.status];
              const StatusIcon = status.icon;

              return (
                <tr key={exp.id}>
                  <td>
                    <Link
                      to={`/experiments/${exp.id}`}
                      className="hover:text-black transition-colors"
                    >
                      <span className="text-[#999] font-mono text-[11px] mr-1.5">#{exp.id}</span>
                      <span className="font-medium text-[#333]">{exp.name || `Experiment #${exp.id}`}</span>
                    </Link>
                    {(exp.tags ?? []).slice(0, 2).map((tag) => (
                      <span
                        key={tag}
                        className="ml-2 px-2 py-0.5 text-[9px] font-semibold tracking-[0.1em] uppercase bg-[#f5f5f5] text-[#666]"
                      >
                        {tag}
                      </span>
                    ))}
                  </td>
                  <td className="font-mono text-[11px] text-[#666]">{exp.model_name}</td>
                  <td>
                    <div className="flex items-center gap-2">
                      <StatusIcon
                        className={clsx(
                          'w-3.5 h-3.5',
                          status.color,
                          status.animate && 'animate-spin'
                        )}
                      />
                      <span className={clsx('text-[11px] font-medium', status.color)}>
                        {status.label}
                      </span>
                    </div>
                  </td>
                  <td className="text-right text-[11px] text-[#999]">
                    {formatDistanceToNow(new Date(exp.created_at), { addSuffix: true })}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {experiments.length === 0 && (
        <div className="px-6 py-16 text-center">
          <p className="text-[#999] text-[11px] tracking-[0.1em] uppercase">No experiments yet</p>
          <Link
            to="/experiments/new"
            className="mt-4 inline-flex items-center gap-2 text-[11px] font-semibold tracking-[0.1em] uppercase text-black hover:text-[#c5a47e] transition-colors"
          >
            Create your first experiment
            <ArrowRight className="w-3.5 h-3.5" />
          </Link>
        </div>
      )}
    </div>
  );
}
