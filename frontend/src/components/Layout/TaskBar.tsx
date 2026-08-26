import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Brain,
  FileText,
  Loader2,
  CheckCircle2,
  XCircle,
  ChevronDown,
  ChevronUp,
  X,
  Trash2,
} from 'lucide-react';
import clsx from 'clsx';
import { useBackgroundTasks, type BackgroundTask, type TaskKind } from '../../context/BackgroundTasks';

const KIND_META: Record<TaskKind, { icon: typeof Brain; color: string; bg: string }> = {
  'scientist-single': { icon: Brain, color: 'text-black', bg: 'bg-[#f5f5f5]' },
  'scientist-full': { icon: Brain, color: 'text-[#c5a47e]', bg: 'bg-[#faf6f0]' },
  report: { icon: FileText, color: 'text-[#666]', bg: 'bg-[#f5f5f5]' },
  'ultimate-report': { icon: Brain, color: 'text-[#c5a47e]', bg: 'bg-[#faf6f0]' },
};

function elapsed(ms: number): string {
  const s = Math.floor(ms / 1000);
  if (s < 60) return `${s}s`;
  const m = Math.floor(s / 60);
  return `${m}m ${s % 60}s`;
}

function TaskRow({ task, onDismiss }: { task: BackgroundTask; onDismiss: () => void }) {
  const navigate = useNavigate();
  const meta = KIND_META[task.kind];
  const Icon = meta.icon;
  const duration = task.finishedAt ? task.finishedAt - task.startedAt : Date.now() - task.startedAt;

  const handleClick = () => {
    if (task.kind === 'scientist-single' || task.kind === 'scientist-full') {
      navigate('/scientist');
    } else if (task.experimentId) {
      navigate(`/experiments/${task.experimentId}`);
    }
  };

  return (
    <div
      className={clsx(
        'flex items-center gap-3 px-3 py-2 cursor-pointer transition-colors',
        task.status === 'running' && 'bg-[#faf6f0]/50 hover:bg-[#faf6f0]',
        task.status === 'completed' && 'bg-[#f0fdf4]/50 hover:bg-[#f0fdf4]',
        task.status === 'error' && 'bg-[#fef2f2]/50 hover:bg-[#fef2f2]',
      )}
      onClick={handleClick}
    >
      <div className={clsx('p-1.5', meta.bg)}>
        {task.status === 'running' ? (
          <Loader2 className={clsx('w-3.5 h-3.5 animate-spin', meta.color)} />
        ) : (
          <Icon className={clsx('w-3.5 h-3.5', meta.color)} />
        )}
      </div>

      <div className="flex-1 min-w-0">
        <p className="text-[11px] font-medium text-black truncate">{task.label}</p>
        <div className="flex items-center gap-2 text-[10px] text-[#999]">
          {task.status === 'running' && (
            <>
              <span className="flex items-center gap-1">
                <span className="w-1.5 h-1.5 rounded-full bg-[#c5a47e] animate-pulse" />
                <span className="text-[#c5a47e] font-medium">Running</span>
              </span>
              <span>{elapsed(duration)}</span>
            </>
          )}
          {task.status === 'completed' && (
            <>
              <CheckCircle2 className="w-3 h-3 text-[#22c55e]" />
              <span className="text-[#22c55e]">Done</span>
              <span>{elapsed(duration)}</span>
            </>
          )}
          {task.status === 'error' && (
            <>
              <XCircle className="w-3 h-3 text-[#dc2626]" />
              <span className="text-[#dc2626] truncate">{task.error?.slice(0, 40)}</span>
            </>
          )}
        </div>
      </div>

      {task.status !== 'running' && (
        <button
          onClick={(e) => {
            e.stopPropagation();
            onDismiss();
          }}
          className="p-1 text-[#ccc] hover:text-[#666] transition-colors"
        >
          <X className="w-3.5 h-3.5" />
        </button>
      )}
    </div>
  );
}

export default function TaskBar() {
  const { tasks, runningCount, dismiss, clearCompleted } = useBackgroundTasks();
  const [expanded, setExpanded] = useState(false);

  if (tasks.length === 0) return null;

  const completedCount = tasks.filter((t) => t.status !== 'running').length;

  return (
    <div className="fixed bottom-0 left-60 right-0 z-50">
      <button
        onClick={() => setExpanded(!expanded)}
        className={clsx(
          'w-full flex items-center justify-between px-5 py-2.5 border-t transition-colors',
          runningCount > 0
            ? 'bg-black text-white border-[#333]'
            : 'bg-white text-[#333] border-[#e5e5e5]',
        )}
      >
        <div className="flex items-center gap-3">
          {runningCount > 0 && <Loader2 className="w-4 h-4 animate-spin text-[#c5a47e]" />}
          <span className="text-[11px] font-semibold tracking-[0.1em] uppercase">
            {runningCount > 0
              ? `${runningCount} task${runningCount > 1 ? 's' : ''} running`
              : `${completedCount} task${completedCount > 1 ? 's' : ''} completed`}
          </span>
        </div>
        <div className="flex items-center gap-2">
          {completedCount > 0 && !expanded && (
            <span
              className={clsx(
                'text-[10px] font-semibold tracking-[0.1em] uppercase px-2 py-0.5',
                runningCount > 0 ? 'bg-[#333] text-[#999]' : 'bg-[#f5f5f5] text-[#999]',
              )}
            >
              {tasks.length} total
            </span>
          )}
          {expanded ? <ChevronDown className="w-4 h-4" /> : <ChevronUp className="w-4 h-4" />}
        </div>
      </button>

      {expanded && (
        <div className="bg-white border-t border-[#e5e5e5] shadow-[0_-4px_20px_rgba(0,0,0,0.06)] max-h-72 overflow-y-auto">
          <div className="p-3 space-y-1">
            {tasks.map((task) => (
              <TaskRow key={task.id} task={task} onDismiss={() => dismiss(task.id)} />
            ))}
          </div>
          {completedCount > 0 && (
            <div className="px-3 pb-3">
              <button
                onClick={clearCompleted}
                className="flex items-center gap-1.5 text-[10px] font-semibold tracking-[0.1em] uppercase text-[#999] hover:text-black transition-colors"
              >
                <Trash2 className="w-3 h-3" />
                Clear completed
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
