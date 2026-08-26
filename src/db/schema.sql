-- LLM Quant Lab Database Schema
-- PostgreSQL schema for experiment tracking

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================================================
-- Experiments table
-- ============================================================================
CREATE TABLE IF NOT EXISTS experiments (
    id SERIAL PRIMARY KEY,
    uuid UUID DEFAULT uuid_generate_v4() UNIQUE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    
    -- Experiment metadata
    name VARCHAR(255),
    description TEXT,
    git_sha VARCHAR(40),
    git_branch VARCHAR(255),
    
    -- Model information
    model_name VARCHAR(255) NOT NULL,
    model_path TEXT,
    base_precision VARCHAR(20) DEFAULT 'fp16',
    
    -- Hardware context
    hardware_profile VARCHAR(100),
    gpu_type VARCHAR(100),
    gpu_count INTEGER DEFAULT 1,
    
    -- Experiment status
    status VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending', 'running', 'completed', 'failed', 'cancelled')),
    error_message TEXT,
    
    -- User notes
    notes TEXT,
    tags TEXT[]  -- Array of tags for filtering
);

-- Index for common queries
CREATE INDEX IF NOT EXISTS idx_experiments_model_name ON experiments(model_name);
CREATE INDEX IF NOT EXISTS idx_experiments_status ON experiments(status);
CREATE INDEX IF NOT EXISTS idx_experiments_created_at ON experiments(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_experiments_tags ON experiments USING GIN(tags);
-- NOTE: indexes on config_hash and wandb_run_id are created after ALTER TABLE adds the columns (see below)

-- ============================================================================
-- Quantization configurations table
-- ============================================================================
CREATE TABLE IF NOT EXISTS quant_configs (
    id SERIAL PRIMARY KEY,
    experiment_id INTEGER NOT NULL REFERENCES experiments(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    
    -- Method identification
    method_name VARCHAR(100) NOT NULL,
    method_version VARCHAR(50),
    
    -- Quantization parameters
    bit_width INTEGER NOT NULL,
    per_channel BOOLEAN DEFAULT TRUE,
    is_symmetric BOOLEAN DEFAULT TRUE,
    group_size INTEGER,
    
    -- Activation and KV quantization
    activation_quant BOOLEAN DEFAULT FALSE,
    activation_bits INTEGER,
    kv_quant BOOLEAN DEFAULT FALSE,
    kv_bits INTEGER,
    
    -- Stacking information
    stack_order INTEGER DEFAULT 0,  -- Order in stack (0 = first)
    parent_config_id INTEGER REFERENCES quant_configs(id),  -- Previous method in stack
    
    -- Full configuration JSON
    config_json JSONB NOT NULL DEFAULT '{}',
    
    -- Calibration info
    calib_dataset VARCHAR(100),
    calib_size INTEGER,
    calib_seq_length INTEGER,
    
    -- Status
    status VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending', 'running', 'completed', 'failed', 'skipped')),
    error_message TEXT,
    
    -- Timing
    duration_seconds FLOAT
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_quant_configs_experiment_id ON quant_configs(experiment_id);
CREATE INDEX IF NOT EXISTS idx_quant_configs_method_name ON quant_configs(method_name);
CREATE INDEX IF NOT EXISTS idx_quant_configs_bit_width ON quant_configs(bit_width);

-- ============================================================================
-- Metrics table
-- ============================================================================
CREATE TABLE IF NOT EXISTS metrics (
    id SERIAL PRIMARY KEY,
    experiment_id INTEGER NOT NULL REFERENCES experiments(id) ON DELETE CASCADE,
    quant_config_id INTEGER REFERENCES quant_configs(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    
    -- Metric identification
    dataset VARCHAR(100) NOT NULL,
    split VARCHAR(50) DEFAULT 'test',
    metric_name VARCHAR(100) NOT NULL,
    
    -- Metric value
    value DOUBLE PRECISION NOT NULL,
    
    -- Additional context
    extra_metadata JSONB DEFAULT '{}'
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_metrics_experiment_id ON metrics(experiment_id);
CREATE INDEX IF NOT EXISTS idx_metrics_quant_config_id ON metrics(quant_config_id);
CREATE INDEX IF NOT EXISTS idx_metrics_dataset ON metrics(dataset);
CREATE INDEX IF NOT EXISTS idx_metrics_metric_name ON metrics(metric_name);

-- ============================================================================
-- Hardware statistics table
-- ============================================================================
CREATE TABLE IF NOT EXISTS hardware_stats (
    id SERIAL PRIMARY KEY,
    experiment_id INTEGER NOT NULL REFERENCES experiments(id) ON DELETE CASCADE,
    quant_config_id INTEGER REFERENCES quant_configs(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    
    -- Hardware identification
    gpu_type VARCHAR(100),
    gpu_memory_gb FLOAT,
    
    -- Latency measurements (in milliseconds)
    latency_p50 DOUBLE PRECISION,
    latency_p95 DOUBLE PRECISION,
    latency_p99 DOUBLE PRECISION,
    latency_mean DOUBLE PRECISION,
    latency_std DOUBLE PRECISION,
    
    -- Throughput
    tokens_per_second DOUBLE PRECISION,
    batch_size INTEGER,
    sequence_length INTEGER,
    
    -- Memory usage (in GB)
    memory_allocated DOUBLE PRECISION,
    memory_reserved DOUBLE PRECISION,
    memory_peak DOUBLE PRECISION,
    
    -- Power measurements (in Watts)
    power_avg DOUBLE PRECISION,
    power_peak DOUBLE PRECISION,
    energy_joules DOUBLE PRECISION,
    
    -- Model size
    model_size_mb DOUBLE PRECISION,
    quantized_size_mb DOUBLE PRECISION,
    compression_ratio DOUBLE PRECISION,
    
    -- Additional context
    extra_metadata JSONB DEFAULT '{}'
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_hardware_stats_experiment_id ON hardware_stats(experiment_id);
CREATE INDEX IF NOT EXISTS idx_hardware_stats_quant_config_id ON hardware_stats(quant_config_id);

-- ============================================================================
-- Layer-wise metrics table
-- ============================================================================
CREATE TABLE IF NOT EXISTS layer_metrics (
    id SERIAL PRIMARY KEY,
    experiment_id INTEGER NOT NULL REFERENCES experiments(id) ON DELETE CASCADE,
    quant_config_id INTEGER REFERENCES quant_configs(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    
    -- Layer identification
    layer_index INTEGER NOT NULL,
    layer_name VARCHAR(255),
    layer_type VARCHAR(100),
    
    -- Statistic identification
    stat_name VARCHAR(100) NOT NULL,
    stat_type VARCHAR(50) DEFAULT 'weight',  -- 'weight', 'activation', 'kv_cache'
    
    -- Statistic value
    value DOUBLE PRECISION NOT NULL,
    
    -- Optional histogram data
    histogram_bins DOUBLE PRECISION[],
    histogram_counts INTEGER[],
    
    -- Additional context
    extra_metadata JSONB DEFAULT '{}'
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_layer_metrics_experiment_id ON layer_metrics(experiment_id);
CREATE INDEX IF NOT EXISTS idx_layer_metrics_quant_config_id ON layer_metrics(quant_config_id);
CREATE INDEX IF NOT EXISTS idx_layer_metrics_layer_index ON layer_metrics(layer_index);
CREATE INDEX IF NOT EXISTS idx_layer_metrics_stat_name ON layer_metrics(stat_name);

-- ============================================================================
-- Scientist reports table
-- ============================================================================
CREATE TABLE IF NOT EXISTS scientist_reports (
    id SERIAL PRIMARY KEY,
    experiment_id INTEGER NOT NULL REFERENCES experiments(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    
    -- LLM information
    llm_model VARCHAR(100),
    llm_provider VARCHAR(100),
    
    -- Prompt and response
    prompt_payload_json JSONB NOT NULL,
    report_markdown TEXT NOT NULL,
    
    -- Extracted information
    summary TEXT,
    pass_fail VARCHAR(20) CHECK (pass_fail IN ('pass', 'fail', 'inconclusive', 'unknown')),
    confidence_score DOUBLE PRECISION,
    
    -- Reasoning and tags
    reasoning_tags TEXT[],
    key_findings TEXT[],
    suggested_experiments TEXT[],
    
    -- Token usage
    prompt_tokens INTEGER,
    completion_tokens INTEGER,
    total_tokens INTEGER,
    
    -- Additional context
    extra_metadata JSONB DEFAULT '{}'
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_scientist_reports_experiment_id ON scientist_reports(experiment_id);
CREATE INDEX IF NOT EXISTS idx_scientist_reports_pass_fail ON scientist_reports(pass_fail);
CREATE INDEX IF NOT EXISTS idx_scientist_reports_reasoning_tags ON scientist_reports USING GIN(reasoning_tags);

-- ============================================================================
-- Paper notes table (for tracking paper references)
-- ============================================================================
CREATE TABLE IF NOT EXISTS paper_notes (
    id SERIAL PRIMARY KEY,
    paper_id VARCHAR(100) UNIQUE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    
    -- Paper information
    title TEXT NOT NULL,
    authors TEXT[],
    year INTEGER,
    venue VARCHAR(255),
    arxiv_id VARCHAR(50),
    doi VARCHAR(100),
    
    -- Content
    citation TEXT,
    core_idea TEXT,
    relevant_equations TEXT,
    expected_behavior TEXT,
    known_limitations TEXT,
    
    -- Method mapping
    method_names TEXT[],  -- Which quantization methods this paper describes
    
    -- Tags and metadata
    tags TEXT[],
    extra_metadata JSONB DEFAULT '{}'
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_paper_notes_paper_id ON paper_notes(paper_id);
CREATE INDEX IF NOT EXISTS idx_paper_notes_method_names ON paper_notes USING GIN(method_names);
CREATE INDEX IF NOT EXISTS idx_paper_notes_tags ON paper_notes USING GIN(tags);

-- ============================================================================
-- Environment snapshots table (reproducibility)
-- ============================================================================
CREATE TABLE IF NOT EXISTS environment_snapshots (
    id SERIAL PRIMARY KEY,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,

    -- Software versions
    python_version VARCHAR(50),
    pytorch_version VARCHAR(50),
    cuda_version VARCHAR(50),
    rocm_version VARCHAR(50),
    transformers_version VARCHAR(50),
    lightcompress_version VARCHAR(50),

    -- Hardware info
    gpu_name VARCHAR(255),
    gpu_driver VARCHAR(100),
    gpu_count INTEGER,
    cpu_model VARCHAR(255),
    ram_gb DOUBLE PRECISION,

    -- Full snapshot
    pip_freeze TEXT,
    git_sha VARCHAR(40),
    git_branch VARCHAR(255),
    git_diff_hash VARCHAR(64),
    env_hash VARCHAR(64) UNIQUE
);

-- ============================================================================
-- Experiment groups table (ablations / paper tables)
-- ============================================================================
CREATE TABLE IF NOT EXISTS experiment_groups (
    id SERIAL PRIMARY KEY,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    name VARCHAR(255) NOT NULL UNIQUE,
    description TEXT,
    group_type VARCHAR(50),  -- 'ablation', 'comparison', 'paper_table', 'sweep'
    metadata_json JSONB DEFAULT '{}'
);

-- Add W&B cross-reference and reproducibility columns to experiments
ALTER TABLE experiments ADD COLUMN IF NOT EXISTS wandb_run_id VARCHAR(50);
ALTER TABLE experiments ADD COLUMN IF NOT EXISTS wandb_run_url TEXT;
ALTER TABLE experiments ADD COLUMN IF NOT EXISTS wandb_project VARCHAR(100);
ALTER TABLE experiments ADD COLUMN IF NOT EXISTS config_hash VARCHAR(64);
ALTER TABLE experiments ADD COLUMN IF NOT EXISTS environment_id INTEGER REFERENCES environment_snapshots(id);
ALTER TABLE experiments ADD COLUMN IF NOT EXISTS group_id INTEGER REFERENCES experiment_groups(id);
ALTER TABLE experiments ADD COLUMN IF NOT EXISTS seed INTEGER;

-- Indexes on columns added by ALTER TABLE
CREATE INDEX IF NOT EXISTS idx_experiments_config_hash ON experiments(config_hash);
CREATE INDEX IF NOT EXISTS idx_experiments_wandb_run_id ON experiments(wandb_run_id);

-- ============================================================================
-- Calibration records table
-- ============================================================================
CREATE TABLE IF NOT EXISTS calibration_records (
    id SERIAL PRIMARY KEY,
    experiment_id INTEGER NOT NULL REFERENCES experiments(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,

    dataset_name VARCHAR(100) NOT NULL,
    dataset_split VARCHAR(50) DEFAULT 'train',
    num_samples INTEGER NOT NULL,
    sequence_length INTEGER,
    data_hash VARCHAR(64),
    seed INTEGER,
    extra_metadata JSONB DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_calibration_records_experiment_id ON calibration_records(experiment_id);

-- ============================================================================
-- W&B sync audit log
-- ============================================================================
CREATE TABLE IF NOT EXISTS wandb_sync_log (
    id SERIAL PRIMARY KEY,
    experiment_id INTEGER REFERENCES experiments(id) ON DELETE CASCADE,
    sync_direction VARCHAR(10),  -- 'pg_to_wb' or 'wb_to_pg'
    sync_type VARCHAR(50),       -- 'metrics', 'artifacts', 'config'
    synced_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    status VARCHAR(20) DEFAULT 'success',
    details JSONB DEFAULT '{}'
);

-- ============================================================================
-- Knowledge graph tables
-- ============================================================================
CREATE TABLE IF NOT EXISTS knowledge_nodes (
    id VARCHAR(100) PRIMARY KEY,
    label VARCHAR(255) NOT NULL,
    node_type VARCHAR(50) NOT NULL,  -- 'data_type', 'hardware', 'scheme', 'algorithm'
    category VARCHAR(100),
    metadata_json JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL
);

CREATE TABLE IF NOT EXISTS knowledge_edges (
    id SERIAL PRIMARY KEY,
    source_id VARCHAR(100) REFERENCES knowledge_nodes(id),
    target_id VARCHAR(100) REFERENCES knowledge_nodes(id),
    edge_type VARCHAR(50) NOT NULL,
    strength FLOAT DEFAULT 0.5,
    metadata_json JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    UNIQUE(source_id, target_id, edge_type)
);

CREATE INDEX IF NOT EXISTS idx_knowledge_edges_source ON knowledge_edges(source_id);
CREATE INDEX IF NOT EXISTS idx_knowledge_edges_target ON knowledge_edges(target_id);
CREATE INDEX IF NOT EXISTS idx_knowledge_nodes_type ON knowledge_nodes(node_type);

-- ============================================================================
-- Updated_at trigger function
-- ============================================================================
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply trigger to experiments table
DROP TRIGGER IF EXISTS update_experiments_updated_at ON experiments;
CREATE TRIGGER update_experiments_updated_at
    BEFORE UPDATE ON experiments
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Apply trigger to paper_notes table
DROP TRIGGER IF EXISTS update_paper_notes_updated_at ON paper_notes;
CREATE TRIGGER update_paper_notes_updated_at
    BEFORE UPDATE ON paper_notes
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- Views for common queries
-- ============================================================================

-- Experiment summary view
CREATE OR REPLACE VIEW experiment_summary AS
SELECT 
    e.id,
    e.uuid,
    e.name,
    e.model_name,
    e.status,
    e.created_at,
    COUNT(DISTINCT qc.id) AS num_configs,
    COUNT(DISTINCT m.id) AS num_metrics,
    COUNT(DISTINCT sr.id) AS num_reports,
    ARRAY_AGG(DISTINCT qc.method_name) FILTER (WHERE qc.method_name IS NOT NULL) AS methods_used,
    MIN(m.value) FILTER (WHERE m.metric_name = 'perplexity') AS best_perplexity
FROM experiments e
LEFT JOIN quant_configs qc ON e.id = qc.experiment_id
LEFT JOIN metrics m ON e.id = m.experiment_id
LEFT JOIN scientist_reports sr ON e.id = sr.experiment_id
GROUP BY e.id, e.uuid, e.name, e.model_name, e.status, e.created_at;

-- Method comparison view
CREATE OR REPLACE VIEW method_comparison AS
SELECT 
    qc.method_name,
    qc.bit_width,
    e.model_name,
    m.dataset,
    m.metric_name,
    AVG(m.value) AS avg_value,
    MIN(m.value) AS min_value,
    MAX(m.value) AS max_value,
    COUNT(*) AS num_experiments
FROM quant_configs qc
JOIN experiments e ON qc.experiment_id = e.id
JOIN metrics m ON qc.id = m.quant_config_id
WHERE e.status = 'completed'
GROUP BY qc.method_name, qc.bit_width, e.model_name, m.dataset, m.metric_name;
