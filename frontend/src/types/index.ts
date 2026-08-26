// API Types for LLM Quant Lab

export interface Experiment {
  id: number;
  name: string | null;
  description: string | null;
  model_name: string;
  model_path: string | null;
  base_precision: string;
  hardware_profile: string | null;
  gpu_type: string | null;
  gpu_count: number;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';
  git_sha: string | null;
  git_branch: string | null;
  notes: string | null;
  tags: string[];
  error_message: string | null;
  created_at: string;
  updated_at: string | null;
  // W&B cross-references
  wandb_run_id: string | null;
  wandb_run_url: string | null;
  wandb_project: string | null;
  // Reproducibility
  config_hash: string | null;
  environment_id: number | null;
  seed: number | null;
}

export interface QuantConfig {
  id: number;
  experiment_id: number;
  method_name: string;
  method_version: string | null;
  bit_width: number;
  per_channel: boolean;
  is_symmetric: boolean;
  group_size: number | null;
  activation_quant: boolean;
  activation_bits: number | null;
  kv_quant: boolean;
  kv_bits: number | null;
  stack_order: number;
  parent_config_id: number | null;
  config_json: Record<string, unknown>;
  calib_dataset: string | null;
  calib_size: number | null;
  calib_seq_length: number | null;
  status: string;
  duration_seconds: number | null;
  error_message: string | null;
  created_at: string;
}

export interface Metric {
  id: number;
  experiment_id: number;
  quant_config_id: number | null;
  dataset: string;
  split: string;
  metric_name: string;
  value: number;
  metadata: Record<string, unknown>;
  created_at: string;
}

export interface HardwareStat {
  id: number;
  experiment_id: number;
  quant_config_id: number | null;
  gpu_type: string | null;
  gpu_memory_gb: number | null;
  latency_p50: number | null;
  latency_p95: number | null;
  latency_p99: number | null;
  latency_mean: number | null;
  latency_std: number | null;
  tokens_per_second: number | null;
  batch_size: number | null;
  sequence_length: number | null;
  memory_allocated: number | null;
  memory_reserved: number | null;
  memory_peak: number | null;
  power_avg: number | null;
  power_peak: number | null;
  energy_joules: number | null;
  model_size_mb: number | null;
  quantized_size_mb: number | null;
  compression_ratio: number | null;
  created_at: string;
}

export interface LayerMetric {
  id: number;
  experiment_id: number;
  quant_config_id: number | null;
  layer_index: number;
  layer_name: string | null;
  layer_type: string | null;
  stat_name: string;
  stat_type: string;
  value: number;
  histogram_bins: number[] | null;
  histogram_counts: number[] | null;
  created_at: string;
}

export interface ScientistReport {
  id: number;
  experiment_id: number;
  llm_model: string | null;
  llm_provider: string | null;
  prompt_payload_json: Record<string, unknown>;
  report_markdown: string;
  summary: string | null;
  pass_fail: 'pass' | 'fail' | 'inconclusive' | 'unknown' | null;
  confidence_score: number | null;
  reasoning_tags: string[];
  key_findings: string[];
  suggested_experiments: string[];
  prompt_tokens: number | null;
  completion_tokens: number | null;
  total_tokens: number | null;
  created_at: string;
}

export interface ExperimentDetail {
  experiment: Experiment;
  quant_configs: QuantConfig[];
  metrics: Metric[];
  hardware_stats: HardwareStat[];
  layer_metrics: LayerMetric[];
  scientist_reports: ScientistReport[];
}

export interface QuantMethod {
  name: string;
  category: 'weight_only' | 'weight_activation' | 'kv_cache' | 'mixed';
  supported_bit_widths: number[];
  requires_calibration: boolean;
  description: string;
  available: boolean;
}

export interface DashboardStats {
  total_experiments: number;
  completed_experiments: number;
  running_experiments: number;
  failed_experiments: number;
  total_models: number;
  avg_compression_ratio: number;
  avg_perplexity: number;
  recent_experiments: Experiment[];
}

// Chart data types
export interface PerplexityVsBitwidthData {
  method: string;
  bit_width: number;
  perplexity: number;
}

export interface ParetoPoint {
  method: string;
  bit_width: number;
  perplexity: number;
  latency_p50: number;
  tokens_per_second: number;
  compression_ratio: number;
}

export interface LayerStatsData {
  layer_index: number;
  layer_name: string;
  pre_quant_norm: number;
  post_quant_norm: number;
  quantization_error: number;
}

// ─── Knowledge Graph ─────────────────────────────────────────────────
export interface KnowledgeNode {
  id: string;
  label: string;
  node_type: 'data_type' | 'hardware' | 'scheme' | 'algorithm';
  category: string;
  metadata_json: Record<string, unknown>;
}

export interface KnowledgeEdge {
  id: number;
  source_id: string;
  target_id: string;
  edge_type: string;
  strength: number;
  metadata_json: Record<string, unknown>;
}

export interface KnowledgeGraphData {
  nodes: KnowledgeNode[];
  edges: KnowledgeEdge[];
}

// ─── Model Registry ──────────────────────────────────────────────────
export interface ModelInfo {
  hf_id: string;
  architecture: string;
  llmc_type: string | null;
  is_llmc_compatible: boolean;
  downloads: number;
  likes: number;
  size_category: string;
  pipeline_tag: string | null;
  tags: string[];
}

// ─── Scientist Analysis ──────────────────────────────────────────────
export interface Finding {
  title: string;
  description: string;
  evidence: string;
  confidence: number;
  category: string;
}

export interface FollowUpExperiment {
  description: string;
  config: Record<string, unknown>;
  rationale: string;
  priority: number;
}

export interface AnalysisResult {
  question: string;
  findings: Finding[];
  follow_up_experiments: FollowUpExperiment[];
  plots: string[];
  raw_reasoning: string;
}

// ─── Environment ─────────────────────────────────────────────────────
export interface EnvironmentInfo {
  python_version: string;
  pytorch_version: string | null;
  cuda_version: string | null;
  rocm_version: string | null;
  gpu_name: string | null;
  gpu_count: number;
  cpu_model: string | null;
  ram_gb: number;
  env_hash: string;
}
