import { createContext, useContext, useCallback, useRef, useState, type ReactNode } from 'react';
import {
  runScientistAnalysis,
  runFullScientistAnalysis,
  generateReport,
  generateUltimateReport,
} from '../api/client';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type TaskKind = 'scientist-single' | 'scientist-full' | 'report' | 'ultimate-report';

export type TaskStatus = 'running' | 'completed' | 'error';

export interface BackgroundTask {
  id: string;
  kind: TaskKind;
  status: TaskStatus;
  label: string;
  startedAt: number;
  finishedAt?: number;
  /** Arbitrary payload: analysis results, report markdown, etc. */
  result?: unknown;
  error?: string;
  /** For experiment-scoped tasks */
  experimentId?: number;
}

interface BackgroundTasksContextValue {
  tasks: BackgroundTask[];
  runningCount: number;

  /** Launch a single scientist analysis question. */
  startScientistSingle: (question: string) => string;
  /** Launch the full scientist analysis pipeline. */
  startScientistFull: () => string;
  /** Launch a standard report for an experiment. */
  startReport: (experimentId: number) => string;
  /** Launch ultimate analysis for an experiment. */
  startUltimateReport: (experimentId: number) => string;

  /** Dismiss (remove) a completed/errored task. */
  dismiss: (taskId: string) => void;
  /** Clear all completed tasks. */
  clearCompleted: () => void;

  /** Get tasks filtered by kind or experiment. */
  getTasksByKind: (kind: TaskKind) => BackgroundTask[];
  getTasksByExperiment: (experimentId: number) => BackgroundTask[];
}

const Ctx = createContext<BackgroundTasksContextValue | null>(null);

// ---------------------------------------------------------------------------
// Provider
// ---------------------------------------------------------------------------

let _nextId = 1;

export function BackgroundTasksProvider({ children }: { children: ReactNode }) {
  const [tasks, setTasks] = useState<BackgroundTask[]>([]);
  const tasksRef = useRef(tasks);
  tasksRef.current = tasks;

  const upsert = useCallback((id: string, patch: Partial<BackgroundTask>) => {
    setTasks((prev) => {
      const idx = prev.findIndex((t) => t.id === id);
      if (idx === -1) return prev;
      const updated = [...prev];
      updated[idx] = { ...updated[idx], ...patch };
      return updated;
    });
  }, []);

  const addTask = useCallback((kind: TaskKind, label: string, experimentId?: number): string => {
    const id = `task-${_nextId++}-${Date.now()}`;
    const task: BackgroundTask = {
      id,
      kind,
      status: 'running',
      label,
      startedAt: Date.now(),
      experimentId,
    };
    setTasks((prev) => [task, ...prev]);
    return id;
  }, []);

  // ── Scientist single ──────────────────────────────────────────────
  const startScientistSingle = useCallback((question: string): string => {
    const id = addTask('scientist-single', question.length > 60 ? question.slice(0, 60) + '…' : question);
    runScientistAnalysis(question)
      .then((data) => upsert(id, { status: 'completed', result: data, finishedAt: Date.now() }))
      .catch((err) => upsert(id, { status: 'error', error: err instanceof Error ? err.message : String(err), finishedAt: Date.now() }));
    return id;
  }, [addTask, upsert]);

  // ── Scientist full ────────────────────────────────────────────────
  const startScientistFull = useCallback((): string => {
    const id = addTask('scientist-full', 'Full Analysis Pipeline');
    runFullScientistAnalysis()
      .then((data) => upsert(id, { status: 'completed', result: data, finishedAt: Date.now() }))
      .catch((err) => upsert(id, { status: 'error', error: err instanceof Error ? err.message : String(err), finishedAt: Date.now() }));
    return id;
  }, [addTask, upsert]);

  // ── Standard report ───────────────────────────────────────────────
  const startReport = useCallback((experimentId: number): string => {
    const id = addTask('report', `Report #${experimentId}`, experimentId);
    generateReport(experimentId)
      .then((data) => upsert(id, { status: 'completed', result: data, finishedAt: Date.now() }))
      .catch((err) => upsert(id, { status: 'error', error: err instanceof Error ? err.message : String(err), finishedAt: Date.now() }));
    return id;
  }, [addTask, upsert]);

  // ── Ultimate report ───────────────────────────────────────────────
  const startUltimateReport = useCallback((experimentId: number): string => {
    const id = addTask('ultimate-report', `Ultimate Analysis #${experimentId}`, experimentId);
    generateUltimateReport(experimentId, { thinking_budget: 'very_high' })
      .then((data) => upsert(id, { status: 'completed', result: data, finishedAt: Date.now() }))
      .catch((err) => upsert(id, { status: 'error', error: err instanceof Error ? err.message : String(err), finishedAt: Date.now() }));
    return id;
  }, [addTask, upsert]);

  // ── Helpers ───────────────────────────────────────────────────────
  const dismiss = useCallback((taskId: string) => {
    setTasks((prev) => prev.filter((t) => t.id !== taskId));
  }, []);

  const clearCompleted = useCallback(() => {
    setTasks((prev) => prev.filter((t) => t.status === 'running'));
  }, []);

  const getTasksByKind = useCallback(
    (kind: TaskKind) => tasksRef.current.filter((t) => t.kind === kind),
    [],
  );

  const getTasksByExperiment = useCallback(
    (experimentId: number) => tasksRef.current.filter((t) => t.experimentId === experimentId),
    [],
  );

  const runningCount = tasks.filter((t) => t.status === 'running').length;

  return (
    <Ctx.Provider
      value={{
        tasks,
        runningCount,
        startScientistSingle,
        startScientistFull,
        startReport,
        startUltimateReport,
        dismiss,
        clearCompleted,
        getTasksByKind,
        getTasksByExperiment,
      }}
    >
      {children}
    </Ctx.Provider>
  );
}

export function useBackgroundTasks() {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error('useBackgroundTasks must be used inside BackgroundTasksProvider');
  return ctx;
}
