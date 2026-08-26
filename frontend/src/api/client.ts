import axios from 'axios';
import type {
  Experiment,
  ExperimentDetail,
  DashboardStats,
  QuantMethod,
  Metric,
  KnowledgeGraphData,
  ModelInfo,
  AnalysisResult,
  EnvironmentInfo,
} from '../types';

const API_BASE_URL = import.meta.env.VITE_API_URL || '/api';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// ─── Experiments ─────────────────────────────────────────────────────
export async function getExperiments(params?: {
  limit?: number;
  offset?: number;
  status?: string;
  model?: string;
  method?: string;
}): Promise<{ experiments: Experiment[]; total: number }> {
  const { data } = await api.get('/experiments', { params });
  return data;
}

export async function getExperiment(id: number): Promise<ExperimentDetail> {
  const { data } = await api.get(`/experiments/${id}`);
  return data;
}

export async function createExperiment(config: {
  model_path: string;
  quant_methods: string[];
  bit_width: number;
  group_size: number | null;
  symmetric: boolean;
  calib_dataset: string;
  calib_size: number;
  calib_seq_length: number;
  eval_datasets?: string[];
  name?: string;
  notes?: string;
  tags?: string[];
}): Promise<{ experiment_id: number }> {
  const { data } = await api.post('/experiments', config);
  return data;
}

export async function deleteExperiment(id: number): Promise<void> {
  await api.delete(`/experiments/${id}`);
}

// ─── Dashboard ───────────────────────────────────────────────────────
export async function getDashboardStats(): Promise<DashboardStats> {
  const { data } = await api.get('/dashboard/stats');
  return data;
}

// ─── Quantization Methods ────────────────────────────────────────────
export async function getQuantMethods(): Promise<QuantMethod[]> {
  const { data } = await api.get('/quant/methods');
  return data;
}

export async function validateStack(methods: string[]): Promise<{
  valid: boolean;
  reason: string;
  normalized_order: string[];
}> {
  const { data } = await api.post('/quant/validate-stack', { methods });
  return data;
}

// ─── Metrics Comparison ──────────────────────────────────────────────
export async function getMetricsComparison(params: {
  experiment_ids?: number[];
  methods?: string[];
  metric_name?: string;
  dataset?: string;
}): Promise<Metric[]> {
  const { data } = await api.get('/metrics/compare', { params });
  return data;
}

// ─── Reports ─────────────────────────────────────────────────────────
export async function generateReport(experimentId: number, paperIds?: string[]): Promise<{
  report_id: number;
  report_markdown: string;
}> {
  const { data } = await api.post(`/experiments/${experimentId}/report`, { paper_ids: paperIds });
  return data;
}

export async function getReports(params?: {
  limit?: number;
  offset?: number;
}): Promise<{ reports: any[]; total: number }> {
  const { data } = await api.get('/reports', { params });
  return data;
}

// ─── Knowledge Graph ─────────────────────────────────────────────────
export async function getKnowledgeGraph(params?: {
  node_types?: string;
  search?: string;
}): Promise<KnowledgeGraphData> {
  const { data } = await api.get('/knowledge/graph', { params });
  return data;
}

export async function getKnowledgeGraphSeedStatus(): Promise<{ seeded: boolean; node_count: number; edge_count: number }> {
  const { data } = await api.get('/knowledge/graph/seed-status');
  return data;
}

export async function seedKnowledgeGraph(): Promise<{ status: string; nodes: number; edges: number }> {
  const { data } = await api.post('/knowledge/graph/seed');
  return data;
}

// ─── Model Registry ──────────────────────────────────────────────────
export async function searchModels(params: {
  query?: string;
  limit?: number;
  compatible_only?: boolean;
}): Promise<ModelInfo[]> {
  const { data } = await api.get('/models/search', { params });
  return data;
}

export async function getModelCompatibility(modelId: string): Promise<{
  model_id: string;
  architecture: string | null;
  llmc_type: string | null;
  is_compatible: boolean;
}> {
  const { data } = await api.get(`/models/${modelId}/compatibility`);
  return data;
}

// ─── Experiment Launch ────────────────────────────────────────────────
export async function launchExperiment(id: number): Promise<{
  status: string;
  experiment_id: number;
  message: string;
}> {
  const { data } = await api.post(`/experiments/${id}/launch`);
  return data;
}

export async function getExperimentStatus(id: number): Promise<{
  experiment_id: number;
  status: string;
  started_at: string | null;
  elapsed_seconds: number | null;
  error: string | null;
  progress: string | null;
}> {
  const { data } = await api.get(`/experiments/${id}/status`);
  return data;
}

export async function getExperimentLogs(id: number, offset: number = 0, limit: number = 200): Promise<{
  experiment_id: number;
  logs: string[];
  total_lines: number;
}> {
  const { data } = await api.get(`/experiments/${id}/logs`, { params: { offset, limit } });
  return data;
}

// ─── Scientist Analysis ──────────────────────────────────────────────
export async function runScientistAnalysis(question: string): Promise<AnalysisResult> {
  const { data } = await api.post('/scientist/analyze', { question });
  return data;
}

export async function runFullScientistAnalysis(): Promise<AnalysisResult[]> {
  const { data } = await api.post('/scientist/full-analysis');
  return data;
}

// ─── Ultimate Analysis ───────────────────────────────────────────
export async function generateUltimateReport(experimentId: number, options?: {
  thinking_budget?: string;
  include_literature?: boolean;
  include_hardware?: boolean;
  include_layer_analysis?: boolean;
}): Promise<AnalysisResult & {
  experiment_id: number;
  analysis_type: string;
  tool_calls_count: number;
  thinking_turns: number;
}> {
  const { data } = await api.post(`/experiments/${experimentId}/report/ultimate`, options || {});
  return data;
}

// ─── Papers & Literature ─────────────────────────────────────────────
export async function getPapers(): Promise<{
  papers: Array<{ filename: string; title: string; size_mb: number }>;
  notes: Array<Record<string, any>>;
  total: number;
}> {
  const { data } = await api.get('/papers');
  return data;
}

export interface PaperReproductionResult {
  model: string;
  method: string;
  bit_width: number;
  dataset: string;
  metric_name: string;
  value: number;
  table_ref: string | null;
}

export interface PaperReproductionSpec {
  paper_id: string;
  title: string;
  arxiv_id: string;
  models: string[];
  methods: string[];
  bit_widths: number[];
  datasets: string[];
  default_calib_dataset: string;
  default_calib_samples: number;
  default_calib_seq_len: number;
  default_group_size: number | null;
  default_symmetric: boolean;
  notes: string;
  config: Record<string, unknown>;
  results: PaperReproductionResult[];
}

export async function getPaperReproductionSpecs(): Promise<{ specs: PaperReproductionSpec[] }> {
  const { data } = await api.get('/papers/reproduction');
  return data;
}

// ─── Reproduction Summary ────────────────────────────────────────────
export interface ReproductionSummaryData {
  v2_only?: boolean;
  reproduction_v2_min_id?: number | null;
  status_counts?: { total?: number; completed?: number; failed?: number; running?: number; pending?: number };
  verdicts?: { matching?: number; close?: number; better?: number; worse?: number };
  comparisons?: Array<{
    experiment_id: number;
    model: string;
    method: string;
    paper_id: string;
    dataset: string;
    metric: string;
    paper_value: number;
    our_value: number;
    diff_pct: number;
    verdict: string;
  }>;
  experiments?: Array<{
    id: number;
    name: string | null;
    model: string;
    status: string;
    error: string | null;
    paper_id: string | null;
    method: string | null;
    metric_count: number;
    wandb_url: string | null;
  }>;
}

export async function getReproductionSummary(opts?: { v2Only?: boolean }): Promise<ReproductionSummaryData> {
  const params = opts?.v2Only ? { v2_only: true } : {};
  const { data } = await api.get('/papers/reproduction-summary', { params });
  return data ?? {};
}

// ─── Environment ─────────────────────────────────────────────────────
export async function getEnvironment(): Promise<EnvironmentInfo> {
  const { data } = await api.get('/environment/current');
  return data;
}

// ─── Health Check ────────────────────────────────────────────────────
export async function healthCheck(): Promise<{ status: string; version: string }> {
  const { data } = await api.get('/health');
  return data;
}

export interface HealthCheckFull {
  status: string;
  version: string;
  timestamp: string;
  checks: Record<string, {
    status: string;
    message: string;
    [key: string]: unknown;
  }>;
}

export async function healthCheckFull(): Promise<HealthCheckFull> {
  const { data } = await api.get('/health/full');
  return data;
}

// ─── Analytics Data ──────────────────────────────────────────────────
export async function getAnalyticsData(): Promise<{
  perplexity_data: Array<{ method: string; bit_width: number; perplexity: number; experiment_id: number }>;
  pareto_data: Array<{ method: string; bit_width: number; perplexity: number; latency_p50: number; tokens_per_second: number; compression_ratio: number }>;
  layer_data: Array<{ layer_index: number; layer_name: string; stat_name: string; value: number; experiment_id: number }>;
}> {
  const { data } = await api.get('/analytics/data');
  return data;
}

export default api;
