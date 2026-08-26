"""SQLAlchemy ORM models for experiment tracking."""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel
from sqlalchemy import (
    ARRAY,
    Boolean,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import (
    DeclarativeBase,
    Session,
    relationship,
    sessionmaker,
)
from sqlalchemy.sql import func

# ============================================================================
# Database connection
# ============================================================================

_engine = None
_SessionLocal = None


def get_engine(db_url: str | None = None):
    """Get or create the database engine."""
    global _engine
    if _engine is None:
        url = db_url or os.getenv("DATABASE_URL") or os.getenv("DB_URL", "")
        if not url:
            raise RuntimeError(
                "No database URL provided.  Pass db_url or set DATABASE_URL in your .env file."
            )
        _engine = create_engine(url, pool_pre_ping=True, pool_size=5, max_overflow=10)
    return _engine


def get_session(db_url: str | None = None) -> Session:
    """Get a new database session."""
    global _SessionLocal
    if _SessionLocal is None:
        engine = get_engine(db_url)
        _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return _SessionLocal()


# ============================================================================
# Base class
# ============================================================================


class Base(DeclarativeBase):
    """Base class for all models."""
    pass


# ============================================================================
# Enums
# ============================================================================

class ExperimentStatus(str):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class QuantConfigStatus(str):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class PassFail(str):
    PASS = "pass"
    FAIL = "fail"
    INCONCLUSIVE = "inconclusive"
    UNKNOWN = "unknown"


# ============================================================================
# Models
# ============================================================================


class EnvironmentSnapshot(Base):
    """Captured runtime environment for reproducibility."""

    __tablename__ = "environment_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Software versions
    python_version = Column(String(50))
    pytorch_version = Column(String(50))
    cuda_version = Column(String(50))
    rocm_version = Column(String(50))
    transformers_version = Column(String(50))
    lightcompress_version = Column(String(50))

    # Hardware info
    gpu_name = Column(String(255))
    gpu_driver = Column(String(100))
    gpu_count = Column(Integer)
    cpu_model = Column(String(255))
    ram_gb = Column(Float)

    # Full snapshot
    pip_freeze = Column(Text)
    git_sha = Column(String(40))
    git_branch = Column(String(255))
    git_diff_hash = Column(String(64))
    env_hash = Column(String(64), unique=True)

    # Relationships
    experiments = relationship("Experiment", back_populates="environment")

    def __repr__(self) -> str:
        return f"<EnvironmentSnapshot(id={self.id}, env_hash='{self.env_hash}')>"

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "python_version": self.python_version,
            "pytorch_version": self.pytorch_version,
            "cuda_version": self.cuda_version,
            "rocm_version": self.rocm_version,
            "gpu_name": self.gpu_name,
            "gpu_count": self.gpu_count,
            "env_hash": self.env_hash,
        }


class ExperimentGroup(Base):
    """Logical grouping of experiments (e.g. ablation study, paper table)."""

    __tablename__ = "experiment_groups"

    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    name = Column(String(255), nullable=False, unique=True)
    description = Column(Text)
    group_type = Column(String(50))  # 'ablation', 'comparison', 'paper_table', 'sweep'
    metadata_json = Column(JSONB, default={})

    # Relationships
    experiments = relationship(
        "Experiment", back_populates="group", foreign_keys="Experiment.group_id"
    )

    def __repr__(self) -> str:
        return f"<ExperimentGroup(id={self.id}, name='{self.name}')>"

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "group_type": self.group_type,
        }


class Experiment(Base):
    """Experiment tracking model."""
    
    __tablename__ = "experiments"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    uuid = Column(UUID(as_uuid=True), unique=True, nullable=False, server_default=func.uuid_generate_v4())
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Experiment metadata
    name = Column(String(255))
    description = Column(Text)
    git_sha = Column(String(40))
    git_branch = Column(String(255))
    
    # Model information
    model_name = Column(String(255), nullable=False)
    model_path = Column(Text)
    base_precision = Column(String(20), default="fp16")
    
    # Hardware context
    hardware_profile = Column(String(100))
    gpu_type = Column(String(100))
    gpu_count = Column(Integer, default=1)
    
    # Experiment status
    status = Column(String(20), default="pending")
    error_message = Column(Text)
    
    # User notes
    notes = Column(Text)
    tags = Column(ARRAY(Text))

    # --- Unified storage columns (W&B cross-references) ---
    wandb_run_id = Column(String(50))
    wandb_run_url = Column(Text)
    wandb_project = Column(String(100))

    # --- Reproducibility columns ---
    config_hash = Column(String(64))
    environment_id = Column(Integer, ForeignKey("environment_snapshots.id"))
    group_id = Column(Integer, ForeignKey("experiment_groups.id"))
    seed = Column(Integer)
    
    # Relationships
    quant_configs = relationship("QuantConfig", back_populates="experiment", cascade="all, delete-orphan")
    metrics = relationship("Metric", back_populates="experiment", cascade="all, delete-orphan")
    hardware_stats = relationship("HardwareStat", back_populates="experiment", cascade="all, delete-orphan")
    layer_metrics = relationship("LayerMetric", back_populates="experiment", cascade="all, delete-orphan")
    scientist_reports = relationship("ScientistReport", back_populates="experiment", cascade="all, delete-orphan")
    calibration_records = relationship("CalibrationRecord", back_populates="experiment", cascade="all, delete-orphan")
    environment = relationship("EnvironmentSnapshot", back_populates="experiments")
    group = relationship("ExperimentGroup", back_populates="experiments", foreign_keys=[group_id])
    
    def __repr__(self) -> str:
        return f"<Experiment(id={self.id}, name='{self.name}', model='{self.model_name}', status='{self.status}')>"
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "uuid": str(self.uuid) if self.uuid else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "name": self.name,
            "description": self.description,
            "git_sha": self.git_sha,
            "model_name": self.model_name,
            "model_path": self.model_path,
            "base_precision": self.base_precision,
            "hardware_profile": self.hardware_profile,
            "gpu_type": self.gpu_type,
            "status": self.status,
            "notes": self.notes,
            "tags": self.tags,
            "wandb_run_id": self.wandb_run_id,
            "wandb_run_url": self.wandb_run_url,
            "config_hash": self.config_hash,
            "seed": self.seed,
            "group_id": self.group_id,
            "environment_id": self.environment_id,
        }


class QuantConfig(Base):
    """Quantization configuration model."""
    
    __tablename__ = "quant_configs"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    experiment_id = Column(Integer, ForeignKey("experiments.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # Method identification
    method_name = Column(String(100), nullable=False)
    method_version = Column(String(50))
    
    # Quantization parameters
    bit_width = Column(Integer, nullable=False)
    per_channel = Column(Boolean, default=True)
    is_symmetric = Column(Boolean, default=True)
    group_size = Column(Integer)
    
    # Activation and KV quantization
    activation_quant = Column(Boolean, default=False)
    activation_bits = Column(Integer)
    kv_quant = Column(Boolean, default=False)
    kv_bits = Column(Integer)
    
    # Stacking information
    stack_order = Column(Integer, default=0)
    parent_config_id = Column(Integer, ForeignKey("quant_configs.id"))
    
    # Full configuration JSON
    config_json = Column(JSONB, nullable=False, default={})
    
    # Calibration info
    calib_dataset = Column(String(100))
    calib_size = Column(Integer)
    calib_seq_length = Column(Integer)
    
    # Status
    status = Column(String(20), default="pending")
    error_message = Column(Text)
    
    # Timing
    duration_seconds = Column(Float)
    
    # Relationships
    experiment = relationship("Experiment", back_populates="quant_configs")
    metrics = relationship("Metric", back_populates="quant_config", cascade="all, delete-orphan")
    hardware_stats = relationship("HardwareStat", back_populates="quant_config", cascade="all, delete-orphan")
    layer_metrics = relationship("LayerMetric", back_populates="quant_config", cascade="all, delete-orphan")
    parent_config = relationship("QuantConfig", remote_side=[id])
    
    def __repr__(self) -> str:
        return f"<QuantConfig(id={self.id}, method='{self.method_name}', bits={self.bit_width})>"
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "experiment_id": self.experiment_id,
            "method_name": self.method_name,
            "method_version": self.method_version,
            "bit_width": self.bit_width,
            "per_channel": self.per_channel,
            "symmetric": self.is_symmetric,
            "group_size": self.group_size,
            "activation_quant": self.activation_quant,
            "activation_bits": self.activation_bits,
            "kv_quant": self.kv_quant,
            "kv_bits": self.kv_bits,
            "stack_order": self.stack_order,
            "config_json": self.config_json,
            "calib_dataset": self.calib_dataset,
            "calib_size": self.calib_size,
            "status": self.status,
            "duration_seconds": self.duration_seconds,
        }


class Metric(Base):
    """Evaluation metrics model."""
    
    __tablename__ = "metrics"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    experiment_id = Column(Integer, ForeignKey("experiments.id", ondelete="CASCADE"), nullable=False)
    quant_config_id = Column(Integer, ForeignKey("quant_configs.id", ondelete="CASCADE"))
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # Metric identification
    dataset = Column(String(100), nullable=False)
    split = Column(String(50), default="test")
    metric_name = Column(String(100), nullable=False)
    
    # Metric value
    value = Column(Float, nullable=False)
    
    # Additional context
    extra_metadata = Column(JSONB, default={})
    
    # Relationships
    experiment = relationship("Experiment", back_populates="metrics")
    quant_config = relationship("QuantConfig", back_populates="metrics")
    
    def __repr__(self) -> str:
        return f"<Metric(id={self.id}, dataset='{self.dataset}', metric='{self.metric_name}', value={self.value})>"
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "experiment_id": self.experiment_id,
            "quant_config_id": self.quant_config_id,
            "dataset": self.dataset,
            "split": self.split,
            "metric_name": self.metric_name,
            "value": self.value,
            "metadata": self.extra_metadata,
        }


class HardwareStat(Base):
    """Hardware statistics model."""
    
    __tablename__ = "hardware_stats"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    experiment_id = Column(Integer, ForeignKey("experiments.id", ondelete="CASCADE"), nullable=False)
    quant_config_id = Column(Integer, ForeignKey("quant_configs.id", ondelete="CASCADE"))
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # Hardware identification
    gpu_type = Column(String(100))
    gpu_memory_gb = Column(Float)
    
    # Latency measurements (in milliseconds)
    latency_p50 = Column(Float)
    latency_p95 = Column(Float)
    latency_p99 = Column(Float)
    latency_mean = Column(Float)
    latency_std = Column(Float)
    
    # Throughput
    tokens_per_second = Column(Float)
    batch_size = Column(Integer)
    sequence_length = Column(Integer)
    
    # Memory usage (in GB)
    memory_allocated = Column(Float)
    memory_reserved = Column(Float)
    memory_peak = Column(Float)
    
    # Power measurements (in Watts)
    power_avg = Column(Float)
    power_peak = Column(Float)
    energy_joules = Column(Float)
    
    # Model size
    model_size_mb = Column(Float)
    quantized_size_mb = Column(Float)
    compression_ratio = Column(Float)
    
    # Additional context
    extra_metadata = Column(JSONB, default={})
    
    # Relationships
    experiment = relationship("Experiment", back_populates="hardware_stats")
    quant_config = relationship("QuantConfig", back_populates="hardware_stats")
    
    def __repr__(self) -> str:
        return f"<HardwareStat(id={self.id}, gpu='{self.gpu_type}', latency_p50={self.latency_p50})>"
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "experiment_id": self.experiment_id,
            "quant_config_id": self.quant_config_id,
            "gpu_type": self.gpu_type,
            "gpu_memory_gb": self.gpu_memory_gb,
            "latency_p50": self.latency_p50,
            "latency_p95": self.latency_p95,
            "latency_p99": self.latency_p99,
            "latency_mean": self.latency_mean,
            "tokens_per_second": self.tokens_per_second,
            "memory_allocated": self.memory_allocated,
            "memory_peak": self.memory_peak,
            "power_avg": self.power_avg,
            "model_size_mb": self.model_size_mb,
            "quantized_size_mb": self.quantized_size_mb,
            "compression_ratio": self.compression_ratio,
        }


class LayerMetric(Base):
    """Layer-wise metrics model."""
    
    __tablename__ = "layer_metrics"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    experiment_id = Column(Integer, ForeignKey("experiments.id", ondelete="CASCADE"), nullable=False)
    quant_config_id = Column(Integer, ForeignKey("quant_configs.id", ondelete="CASCADE"))
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # Layer identification
    layer_index = Column(Integer, nullable=False)
    layer_name = Column(String(255))
    layer_type = Column(String(100))
    
    # Statistic identification
    stat_name = Column(String(100), nullable=False)
    stat_type = Column(String(50), default="weight")  # 'weight', 'activation', 'kv_cache'
    
    # Statistic value
    value = Column(Float, nullable=False)
    
    # Optional histogram data
    histogram_bins = Column(ARRAY(Float))
    histogram_counts = Column(ARRAY(Integer))
    
    # Additional context
    extra_metadata = Column(JSONB, default={})
    
    # Relationships
    experiment = relationship("Experiment", back_populates="layer_metrics")
    quant_config = relationship("QuantConfig", back_populates="layer_metrics")
    
    def __repr__(self) -> str:
        return f"<LayerMetric(id={self.id}, layer={self.layer_index}, stat='{self.stat_name}', value={self.value})>"
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "experiment_id": self.experiment_id,
            "quant_config_id": self.quant_config_id,
            "layer_index": self.layer_index,
            "layer_name": self.layer_name,
            "layer_type": self.layer_type,
            "stat_name": self.stat_name,
            "stat_type": self.stat_type,
            "value": self.value,
            "histogram_bins": self.histogram_bins,
            "histogram_counts": self.histogram_counts,
        }


class ScientistReport(Base):
    """Scientist LLM report model."""
    
    __tablename__ = "scientist_reports"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    experiment_id = Column(Integer, ForeignKey("experiments.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # LLM information
    llm_model = Column(String(100))
    llm_provider = Column(String(100))
    
    # Prompt and response
    prompt_payload_json = Column(JSONB, nullable=False)
    report_markdown = Column(Text, nullable=False)
    
    # Extracted information
    summary = Column(Text)
    pass_fail = Column(String(20))
    confidence_score = Column(Float)
    
    # Reasoning and tags
    reasoning_tags = Column(ARRAY(Text))
    key_findings = Column(ARRAY(Text))
    suggested_experiments = Column(ARRAY(Text))
    
    # Token usage
    prompt_tokens = Column(Integer)
    completion_tokens = Column(Integer)
    total_tokens = Column(Integer)
    
    # Additional context
    extra_metadata = Column(JSONB, default={})
    
    # Relationships
    experiment = relationship("Experiment", back_populates="scientist_reports")
    
    def __repr__(self) -> str:
        return f"<ScientistReport(id={self.id}, experiment_id={self.experiment_id}, pass_fail='{self.pass_fail}')>"
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "experiment_id": self.experiment_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "llm_model": self.llm_model,
            "llm_provider": self.llm_provider,
            "summary": self.summary,
            "pass_fail": self.pass_fail,
            "confidence_score": self.confidence_score,
            "reasoning_tags": self.reasoning_tags,
            "key_findings": self.key_findings,
            "suggested_experiments": self.suggested_experiments,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
        }


class CalibrationRecord(Base):
    """Record of calibration data used for quantization."""

    __tablename__ = "calibration_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    experiment_id = Column(Integer, ForeignKey("experiments.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    dataset_name = Column(String(100), nullable=False)
    dataset_split = Column(String(50), default="train")
    num_samples = Column(Integer, nullable=False)
    sequence_length = Column(Integer)
    data_hash = Column(String(64))  # SHA-256 of calibration data
    seed = Column(Integer)

    extra_metadata = Column(JSONB, default={})

    # Relationships
    experiment = relationship("Experiment", back_populates="calibration_records")

    def __repr__(self) -> str:
        return f"<CalibrationRecord(id={self.id}, dataset='{self.dataset_name}', n={self.num_samples})>"

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "experiment_id": self.experiment_id,
            "dataset_name": self.dataset_name,
            "num_samples": self.num_samples,
            "sequence_length": self.sequence_length,
            "data_hash": self.data_hash,
            "seed": self.seed,
        }


class WandbSyncLog(Base):
    """Audit log for Postgres <-> W&B sync operations."""

    __tablename__ = "wandb_sync_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    experiment_id = Column(Integer, ForeignKey("experiments.id", ondelete="CASCADE"), nullable=False)
    sync_direction = Column(String(10))  # 'pg_to_wb' or 'wb_to_pg'
    sync_type = Column(String(50))  # 'metrics', 'artifacts', 'config'
    synced_at = Column(DateTime(timezone=True), server_default=func.now())
    status = Column(String(20), default="success")
    details = Column(JSONB, default={})

    def __repr__(self) -> str:
        return f"<WandbSyncLog(id={self.id}, direction='{self.sync_direction}', type='{self.sync_type}')>"


class KnowledgeNode(Base):
    """Node in the quantization knowledge graph."""

    __tablename__ = "knowledge_nodes"

    id = Column(String(100), primary_key=True)
    label = Column(String(255), nullable=False)
    node_type = Column(String(50), nullable=False)  # 'data_type', 'hardware', 'scheme', 'algorithm'
    category = Column(String(100))
    metadata_json = Column(JSONB, default={})
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    def __repr__(self) -> str:
        return f"<KnowledgeNode(id='{self.id}', type='{self.node_type}')>"

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "node_type": self.node_type,
            "category": self.category,
            "metadata": self.metadata_json,
        }


class KnowledgeEdge(Base):
    """Edge in the quantization knowledge graph."""

    __tablename__ = "knowledge_edges"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source_id = Column(String(100), ForeignKey("knowledge_nodes.id"), nullable=False)
    target_id = Column(String(100), ForeignKey("knowledge_nodes.id"), nullable=False)
    edge_type = Column(String(50), nullable=False)  # 'implements', 'uses', 'supports', 'described_in'
    strength = Column(Float, default=0.5)
    metadata_json = Column(JSONB, default={})
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    source = relationship("KnowledgeNode", foreign_keys=[source_id])
    target = relationship("KnowledgeNode", foreign_keys=[target_id])

    def __repr__(self) -> str:
        return f"<KnowledgeEdge(src='{self.source_id}', tgt='{self.target_id}', type='{self.edge_type}')>"

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "source": self.source_id,
            "target": self.target_id,
            "edge_type": self.edge_type,
            "strength": self.strength,
            "metadata": self.metadata_json,
        }


class PaperNote(Base):
    """Paper notes model for tracking paper references."""
    
    __tablename__ = "paper_notes"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    paper_id = Column(String(100), unique=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Paper information
    title = Column(Text, nullable=False)
    authors = Column(ARRAY(Text))
    year = Column(Integer)
    venue = Column(String(255))
    arxiv_id = Column(String(50))
    doi = Column(String(100))
    
    # Content
    citation = Column(Text)
    core_idea = Column(Text)
    relevant_equations = Column(Text)
    expected_behavior = Column(Text)
    known_limitations = Column(Text)
    
    # Method mapping
    method_names = Column(ARRAY(Text))
    
    # Tags and metadata
    tags = Column(ARRAY(Text))
    extra_metadata = Column(JSONB, default={})
    
    def __repr__(self) -> str:
        return f"<PaperNote(id={self.id}, paper_id='{self.paper_id}', title='{self.title[:50]}...')>"
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "paper_id": self.paper_id,
            "title": self.title,
            "authors": self.authors,
            "year": self.year,
            "venue": self.venue,
            "arxiv_id": self.arxiv_id,
            "citation": self.citation,
            "core_idea": self.core_idea,
            "relevant_equations": self.relevant_equations,
            "expected_behavior": self.expected_behavior,
            "known_limitations": self.known_limitations,
            "method_names": self.method_names,
            "tags": self.tags,
        }


# ============================================================================
# Pydantic models for validation
# ============================================================================


class ExperimentCreate(BaseModel):
    """Pydantic model for creating experiments."""
    name: str | None = None
    description: str | None = None
    model_name: str
    model_path: str | None = None
    base_precision: str = "fp16"
    hardware_profile: str | None = None
    notes: str | None = None
    tags: list[str] | None = None


class QuantConfigCreate(BaseModel):
    """Pydantic model for creating quant configs."""
    method_name: str
    bit_width: int
    per_channel: bool = True
    is_symmetric: bool = True
    group_size: int | None = None
    activation_quant: bool = False
    activation_bits: int | None = None
    kv_quant: bool = False
    kv_bits: int | None = None
    config_json: dict[str, Any] = {}
    calib_dataset: str | None = None
    calib_size: int | None = None
    calib_seq_length: int | None = None


class MetricCreate(BaseModel):
    """Pydantic model for creating metrics."""
    dataset: str
    split: str = "test"
    metric_name: str
    value: float
    metadata: dict[str, Any] = {}
