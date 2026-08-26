"""Add unified storage, reproducibility, and knowledge graph tables.

Revision ID: 001
Revises: None
Create Date: 2026-02-08
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- Environment snapshots ---
    op.create_table(
        "environment_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("python_version", sa.String(50)),
        sa.Column("pytorch_version", sa.String(50)),
        sa.Column("cuda_version", sa.String(50)),
        sa.Column("rocm_version", sa.String(50)),
        sa.Column("transformers_version", sa.String(50)),
        sa.Column("lightcompress_version", sa.String(50)),
        sa.Column("gpu_name", sa.String(255)),
        sa.Column("gpu_driver", sa.String(100)),
        sa.Column("gpu_count", sa.Integer()),
        sa.Column("cpu_model", sa.String(255)),
        sa.Column("ram_gb", sa.Float()),
        sa.Column("pip_freeze", sa.Text()),
        sa.Column("git_sha", sa.String(40)),
        sa.Column("git_branch", sa.String(255)),
        sa.Column("git_diff_hash", sa.String(64)),
        sa.Column("env_hash", sa.String(64), unique=True),
    )

    # --- Experiment groups ---
    op.create_table(
        "experiment_groups",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("name", sa.String(255), nullable=False, unique=True),
        sa.Column("description", sa.Text()),
        sa.Column("group_type", sa.String(50)),
        sa.Column("metadata_json", JSONB, server_default="{}"),
    )

    # --- Calibration records ---
    op.create_table(
        "calibration_records",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("experiment_id", sa.Integer(), sa.ForeignKey("experiments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("dataset_name", sa.String(100), nullable=False),
        sa.Column("dataset_split", sa.String(50), server_default="train"),
        sa.Column("num_samples", sa.Integer(), nullable=False),
        sa.Column("sequence_length", sa.Integer()),
        sa.Column("data_hash", sa.String(64)),
        sa.Column("seed", sa.Integer()),
        sa.Column("extra_metadata", JSONB, server_default="{}"),
    )
    op.create_index("idx_calibration_records_experiment_id", "calibration_records", ["experiment_id"])

    # --- W&B sync log ---
    op.create_table(
        "wandb_sync_log",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("experiment_id", sa.Integer(), sa.ForeignKey("experiments.id", ondelete="CASCADE")),
        sa.Column("sync_direction", sa.String(10)),
        sa.Column("sync_type", sa.String(50)),
        sa.Column("synced_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("status", sa.String(20), server_default="success"),
        sa.Column("details", JSONB, server_default="{}"),
    )

    # --- Knowledge graph ---
    op.create_table(
        "knowledge_nodes",
        sa.Column("id", sa.String(100), primary_key=True),
        sa.Column("label", sa.String(255), nullable=False),
        sa.Column("node_type", sa.String(50), nullable=False),
        sa.Column("category", sa.String(100)),
        sa.Column("metadata_json", JSONB, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("idx_knowledge_nodes_type", "knowledge_nodes", ["node_type"])

    op.create_table(
        "knowledge_edges",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("source_id", sa.String(100), sa.ForeignKey("knowledge_nodes.id"), nullable=False),
        sa.Column("target_id", sa.String(100), sa.ForeignKey("knowledge_nodes.id"), nullable=False),
        sa.Column("edge_type", sa.String(50), nullable=False),
        sa.Column("strength", sa.Float(), server_default="0.5"),
        sa.Column("metadata_json", JSONB, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.UniqueConstraint("source_id", "target_id", "edge_type"),
    )
    op.create_index("idx_knowledge_edges_source", "knowledge_edges", ["source_id"])
    op.create_index("idx_knowledge_edges_target", "knowledge_edges", ["target_id"])

    # --- Add columns to experiments ---
    op.add_column("experiments", sa.Column("wandb_run_id", sa.String(50)))
    op.add_column("experiments", sa.Column("wandb_run_url", sa.Text()))
    op.add_column("experiments", sa.Column("wandb_project", sa.String(100)))
    op.add_column("experiments", sa.Column("config_hash", sa.String(64)))
    op.add_column("experiments", sa.Column("environment_id", sa.Integer(), sa.ForeignKey("environment_snapshots.id")))
    op.add_column("experiments", sa.Column("group_id", sa.Integer(), sa.ForeignKey("experiment_groups.id")))
    op.add_column("experiments", sa.Column("seed", sa.Integer()))

    op.create_index("idx_experiments_config_hash", "experiments", ["config_hash"])
    op.create_index("idx_experiments_wandb_run_id", "experiments", ["wandb_run_id"])


def downgrade() -> None:
    op.drop_index("idx_experiments_wandb_run_id", "experiments")
    op.drop_index("idx_experiments_config_hash", "experiments")
    op.drop_column("experiments", "seed")
    op.drop_column("experiments", "group_id")
    op.drop_column("experiments", "environment_id")
    op.drop_column("experiments", "config_hash")
    op.drop_column("experiments", "wandb_project")
    op.drop_column("experiments", "wandb_run_url")
    op.drop_column("experiments", "wandb_run_id")

    op.drop_table("knowledge_edges")
    op.drop_table("knowledge_nodes")
    op.drop_table("wandb_sync_log")
    op.drop_table("calibration_records")
    op.drop_table("experiment_groups")
    op.drop_table("environment_snapshots")
