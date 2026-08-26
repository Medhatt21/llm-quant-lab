"""LLM Quant Lab - CLI entrypoint.

This module provides the command-line interface for running quantization
experiments, generating reports, and managing the experiment database.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.logging import RichHandler
from rich.table import Table

from src.config import get_settings, ConfigurationError

# Load configuration - fail fast with a clear message if invalid.
# When imported as a library (e.g. tests), the error propagates normally.
# When run as the CLI entrypoint, typer's callback handles it.
_settings_error: str | None = None
try:
    settings = get_settings()
    settings.setup_environment()
except ConfigurationError as e:
    _settings_error = str(e)
    settings = None  # type: ignore[assignment]

# Configure logging based on settings (if available)
if settings is not None:
    log_level = getattr(logging, settings.logging.level)
    _use_rich = settings.logging.format == "text"
else:
    log_level = logging.WARNING
    _use_rich = False
logging.basicConfig(
    level=log_level,
    format="%(message)s" if _use_rich else "%(asctime)s %(levelname)s %(name)s %(message)s",
    handlers=[RichHandler(rich_tracebacks=True)] if _use_rich else [logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

# Create Typer app
app = typer.Typer(
    name="llm-quant",
    help="LLM Quantization Research OS - Experiment framework for LLM compression",
    add_completion=False,
)

console = Console()


def _require_settings() -> None:
    """Abort with a clear message if settings failed to load."""
    if _settings_error is not None:
        console.print(
            f"[bold red]Configuration error:[/bold red] {_settings_error}",
            highlight=False,
        )
        raise typer.Exit(code=1)


# ============================================================================
# Run Experiment Command
# ============================================================================


@app.command("run-experiment")
def run_experiment_cmd(
    model_path: str = typer.Option(
        ...,
        "--model-path", "-m",
        help="HuggingFace model ID or local path",
    ),
    quant_techs: str = typer.Option(
        "awq",
        "--quant-techs", "-q",
        help="Quantization methods (comma-separated or 'all')",
    ),
    datasets: str = typer.Option(
        "wikitext2",
        "--datasets", "-d",
        help="Evaluation datasets (comma-separated)",
    ),
    bit_width: int = typer.Option(
        4,
        "--bit-width", "-b",
        help="Bit width for quantization",
    ),
    group_size: int = typer.Option(
        128,
        "--group-size", "-g",
        help="Group size for quantization",
    ),
    calib_dataset: str = typer.Option(
        "wikitext2",
        "--calib-dataset",
        help="Calibration dataset",
    ),
    calib_size: int = typer.Option(
        128,
        "--calib-size",
        help="Number of calibration samples",
    ),
    hardware_profile: str = typer.Option(
        "default",
        "--hardware-profile",
        help="Hardware profile name",
    ),
    capture_activations: bool = typer.Option(
        False,
        "--capture-activations/--no-capture-activations",
        help="Capture activation statistics",
    ),
    capture_kv: bool = typer.Option(
        False,
        "--capture-kv/--no-capture-kv",
        help="Capture KV cache statistics",
    ),
    papers: str = typer.Option(
        "",
        "--papers", "-p",
        help="Paper IDs for context (comma-separated)",
    ),
    notes: str = typer.Option(
        "",
        "--notes", "-n",
        help="Experiment notes",
    ),
    name: str = typer.Option(
        None,
        "--name",
        help="Experiment name",
    ),
    tags: str = typer.Option(
        "",
        "--tags", "-t",
        help="Tags for filtering (comma-separated)",
    ),
    no_scientist_report: bool = typer.Option(
        False,
        "--no-scientist-report",
        help="Skip scientist LLM report generation",
    ),
    device: str = typer.Option(
        "cuda",
        "--device",
        help="Device to run on (cuda, cpu)",
    ),
    run_vllm_benchmark: bool = typer.Option(
        False,
        "--run-vllm-benchmark/--no-vllm-benchmark",
        help="Run vLLM serving benchmarks after quantization",
    ),
    num_gpus: int = typer.Option(
        1,
        "--num-gpus",
        help="Number of GPUs for distributed quantization via torchrun",
        min=1,
    ),
) -> None:
    """Run a quantization experiment."""
    _require_settings()
    from .eval.runner import ExperimentConfig, run_experiment
    
    console.print("[bold blue]LLM Quant Lab - Running Experiment[/bold blue]")
    console.print(f"Model: {model_path}")
    console.print(f"Methods: {quant_techs}")
    console.print(f"Bit width: {bit_width}")
    
    # Parse comma-separated values
    methods = [m.strip() for m in quant_techs.split(",") if m.strip()]
    eval_datasets = [d.strip() for d in datasets.split(",") if d.strip()]
    paper_ids = [p.strip() for p in papers.split(",") if p.strip()]
    tag_list = [t.strip() for t in tags.split(",") if t.strip()]
    
    # Handle 'all' methods
    if "all" in methods:
        from .quant import list_quantizers
        methods = list_quantizers()
        console.print(f"Using all available methods: {methods}")
    
    # Create config
    config = ExperimentConfig(
        model_path=model_path,
        quant_methods=methods,
        bit_width=bit_width,
        group_size=group_size,
        calib_dataset=calib_dataset,
        calib_size=calib_size,
        eval_datasets=eval_datasets,
        hardware_profile=hardware_profile,
        capture_activations=capture_activations,
        capture_kv=capture_kv,
        paper_ids=paper_ids,
        notes=notes if notes else None,
        name=name,
        tags=tag_list,
        generate_scientist_report=not no_scientist_report,
        device=device,
        run_vllm_benchmark=run_vllm_benchmark,
        num_gpus=num_gpus,
    )
    
    # Run experiment
    with console.status("[bold green]Running experiment..."):
        result = run_experiment(config)
    
    # Display results
    console.print()
    if result.status == "completed":
        console.print(f"[bold green]Experiment completed successfully![/bold green]")
    else:
        console.print(f"[bold red]Experiment failed![/bold red]")
    
    console.print(f"Experiment ID: {result.experiment_id}")
    console.print(f"Total time: {result.total_time_seconds:.1f}s")
    
    if result.errors:
        console.print("[yellow]Errors:[/yellow]")
        for error in result.errors:
            console.print(f"  - {error}")
    
    # Generate scientist report if requested
    if not no_scientist_report and result.status == "completed":
        console.print()
        console.print("[bold blue]Generating scientist report...[/bold blue]")
        
        try:
            from .llm_reports import generate_scientist_report
            report = generate_scientist_report(result.experiment_id, paper_ids)
            console.print(f"[green]Report generated: reports/experiment_{result.experiment_id}.md[/green]")
        except Exception as e:
            console.print(f"[yellow]Report generation failed: {e}[/yellow]")


# ============================================================================
# Generate Report Command
# ============================================================================


@app.command("generate-report")
def generate_report_cmd(
    experiment_id: int = typer.Option(
        ...,
        "--experiment-id", "-e",
        help="Experiment ID to generate report for",
    ),
    papers: str = typer.Option(
        "",
        "--papers", "-p",
        help="Paper IDs for context (comma-separated)",
    ),
    output: str = typer.Option(
        None,
        "--output", "-o",
        help="Output file path",
    ),
    regenerate: bool = typer.Option(
        False,
        "--regenerate",
        help="Regenerate even if report exists",
    ),
) -> None:
    """Generate or regenerate a scientist report for an experiment."""
    _require_settings()
    console.print(f"[bold blue]Generating report for experiment {experiment_id}[/bold blue]")
    
    paper_ids = [p.strip() for p in papers.split(",") if p.strip()]
    
    try:
        from .llm_reports import generate_scientist_report
        
        report = generate_scientist_report(experiment_id, paper_ids)
        
        output_path = output or f"reports/experiment_{experiment_id}.md"
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, "w") as f:
            f.write(report.report_markdown if hasattr(report, "report_markdown") else str(report))
        
        console.print(f"[green]Report saved to: {output_path}[/green]")
        
    except Exception as e:
        console.print(f"[red]Failed to generate report: {e}[/red]")
        raise typer.Exit(1)


# ============================================================================
# List Methods Command
# ============================================================================


@app.command("list-methods")
def list_methods_cmd(
    verbose: bool = typer.Option(
        False,
        "--verbose", "-v",
        help="Show detailed information",
    ),
) -> None:
    """List available quantization methods."""
    from .quant import list_quantizers
    from .stacking.compatibility import METHOD_INFO
    
    console.print("[bold blue]Available Quantization Methods[/bold blue]")
    console.print()
    
    methods = list_quantizers()
    
    if verbose:
        table = Table(title="Quantization Methods")
        table.add_column("Method", style="cyan")
        table.add_column("Category", style="green")
        table.add_column("Bit Widths", style="yellow")
        table.add_column("Calibration", style="magenta")
        table.add_column("Description")
        
        for method in methods:
            info = METHOD_INFO.get(method, None)
            if info:
                table.add_row(
                    method,
                    info.category.value,
                    str(info.supported_bit_widths or "any"),
                    "Yes" if info.requires_calibration else "No",
                    info.description[:50] + "..." if len(info.description) > 50 else info.description,
                )
            else:
                table.add_row(method, "-", "-", "-", "-")
        
        console.print(table)
    else:
        for method in methods:
            console.print(f"  - {method}")


# ============================================================================
# Validate Stack Command
# ============================================================================


@app.command("validate-stack")
def validate_stack_cmd(
    methods: str = typer.Option(
        ...,
        "--methods", "-m",
        help="Methods to validate (comma-separated)",
    ),
) -> None:
    """Validate a stack of quantization methods."""
    from .stacking import get_stack_summary, is_stack_valid, normalize_stack_order
    
    method_list = [m.strip() for m in methods.split(",") if m.strip()]
    
    console.print(f"[bold blue]Validating stack: {method_list}[/bold blue]")
    console.print()
    
    valid, reason = is_stack_valid(method_list)
    
    if valid:
        console.print("[green]Stack is valid![/green]")
        
        normalized = normalize_stack_order(method_list)
        console.print(f"Normalized order: {normalized}")
        
        summary = get_stack_summary(method_list)
        console.print(f"Has weight quantization: {summary['has_weight_quant']}")
        console.print(f"Has activation quantization: {summary['has_activation_quant']}")
        console.print(f"Has KV cache quantization: {summary['has_kv_quant']}")
        console.print(f"Requires calibration: {summary['requires_calibration']}")
    else:
        console.print(f"[red]Stack is invalid: {reason}[/red]")
        raise typer.Exit(1)


# ============================================================================
# List Experiments Command
# ============================================================================


@app.command("list-experiments")
def list_experiments_cmd(
    limit: int = typer.Option(
        10,
        "--limit", "-l",
        help="Maximum number of experiments to show",
    ),
    status: str = typer.Option(
        None,
        "--status", "-s",
        help="Filter by status",
    ),
    model: str = typer.Option(
        None,
        "--model", "-m",
        help="Filter by model name",
    ),
) -> None:
    """List recent experiments."""
    _require_settings()
    from .db import Experiment, get_session
    
    session = get_session()
    
    query = session.query(Experiment).order_by(Experiment.created_at.desc())
    
    if status:
        query = query.filter(Experiment.status == status)
    if model:
        query = query.filter(Experiment.model_name.contains(model))
    
    experiments = query.limit(limit).all()
    
    if not experiments:
        console.print("[yellow]No experiments found[/yellow]")
        return
    
    table = Table(title="Recent Experiments")
    table.add_column("ID", style="cyan")
    table.add_column("Name", style="green")
    table.add_column("Model", style="yellow")
    table.add_column("Status", style="magenta")
    table.add_column("Created", style="blue")
    
    for exp in experiments:
        status_style = "green" if exp.status == "completed" else "red" if exp.status == "failed" else "yellow"
        table.add_row(
            str(exp.id),
            exp.name or "-",
            exp.model_name[:30] + "..." if len(exp.model_name) > 30 else exp.model_name,
            f"[{status_style}]{exp.status}[/{status_style}]",
            exp.created_at.strftime("%Y-%m-%d %H:%M") if exp.created_at else "-",
        )
    
    console.print(table)
    session.close()


# ============================================================================
# Show Experiment Command
# ============================================================================


@app.command("show-experiment")
def show_experiment_cmd(
    experiment_id: int = typer.Option(
        ...,
        "--experiment-id", "-e",
        help="Experiment ID to show",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Output as JSON",
    ),
) -> None:
    """Show details of an experiment."""
    _require_settings()
    from .db import get_experiment_with_details, get_session
    
    session = get_session()
    
    data = get_experiment_with_details(session, experiment_id)
    
    if not data:
        console.print(f"[red]Experiment {experiment_id} not found[/red]")
        raise typer.Exit(1)
    
    if json_output:
        console.print(json.dumps(data, indent=2, default=str))
    else:
        exp = data["experiment"]
        
        console.print(f"[bold blue]Experiment {experiment_id}[/bold blue]")
        console.print()
        console.print(f"Name: {exp.get('name', '-')}")
        console.print(f"Model: {exp['model_name']}")
        console.print(f"Status: {exp['status']}")
        console.print(f"Created: {exp.get('created_at', '-')}")
        console.print(f"Hardware: {exp.get('gpu_type', '-')}")
        
        if data["quant_configs"]:
            console.print()
            console.print("[bold]Quantization Configs:[/bold]")
            for qc in data["quant_configs"]:
                console.print(f"  - {qc['method_name']} @ {qc['bit_width']}-bit (status: {qc['status']})")
        
        if data["metrics"]:
            console.print()
            console.print("[bold]Metrics:[/bold]")
            for m in data["metrics"]:
                console.print(f"  - {m['dataset']}/{m['metric_name']}: {m['value']:.4f}")
    
    session.close()


# ============================================================================
# Suggest Mode Command
# ============================================================================


@app.command("suggest-mode")
def suggest_mode_cmd(
    rps: int = typer.Option(
        100,
        "--rps",
        help="Target requests per second",
    ),
    sla_ms: int = typer.Option(
        200,
        "--sla-ms",
        help="Target latency SLA in milliseconds",
    ),
) -> None:
    """Suggest quantization profile based on RPS/SLA requirements."""
    console.print(f"[bold blue]Suggesting profile for RPS={rps}, SLA={sla_ms}ms[/bold blue]")
    console.print()
    
    # Simple heuristic-based suggestions
    if rps > 500 or sla_ms < 50:
        # Beast mode: aggressive quantization
        console.print("[bold green]Suggested: Beast Mode[/bold green]")
        console.print("  Methods: AWQ + KVQuant")
        console.print("  Bit width: 4 (weights), 4 (KV)")
        console.print("  Group size: 128")
        console.print("  Note: Prioritizes throughput over accuracy")
    elif rps > 100 or sla_ms < 100:
        # Normal mode: balanced
        console.print("[bold yellow]Suggested: Normal Mode[/bold yellow]")
        console.print("  Methods: AWQ")
        console.print("  Bit width: 4")
        console.print("  Group size: 128")
        console.print("  Note: Balanced accuracy/performance")
    else:
        # Efficient mode: accuracy-focused
        console.print("[bold cyan]Suggested: Efficient Mode[/bold cyan]")
        console.print("  Methods: GPTQ")
        console.print("  Bit width: 4")
        console.print("  Group size: 128")
        console.print("  Note: Prioritizes accuracy")


# ============================================================================
# Init DB Command
# ============================================================================


@app.command("init-db")
def init_db_cmd() -> None:
    """Initialize the database schema."""
    _require_settings()
    from sqlalchemy import text
    
    from .db import Base, get_engine
    
    console.print("[bold blue]Initializing database...[/bold blue]")
    
    engine = get_engine()
    
    # Create all tables
    Base.metadata.create_all(engine)
    
    # Run schema.sql for additional setup (views, triggers)
    schema_path = Path(__file__).parent / "db" / "schema.sql"
    if schema_path.exists():
        with open(schema_path) as f:
            schema_sql = f.read()
        
        with engine.connect() as conn:
            # Execute statements one by one
            for statement in schema_sql.split(";"):
                statement = statement.strip()
                if statement and not statement.startswith("--"):
                    try:
                        conn.execute(text(statement))
                    except Exception as e:
                        if "already exists" not in str(e).lower():
                            raise RuntimeError(
                                f"Database schema error: {e}. "
                                f"Failed statement: {statement[:100]}..."
                            ) from e
            conn.commit()
    
    console.print("[green]Database initialized successfully![/green]")


# ============================================================================
# Paper Export Command
# ============================================================================


@app.command("paper-export")
def paper_export_cmd(
    group: str = typer.Option(
        None,
        "--group", "-g",
        help="Experiment group name to export",
    ),
    experiment_ids: str = typer.Option(
        None,
        "--experiment-ids", "-e",
        help="Comma-separated experiment IDs to export",
    ),
    output_dir: str = typer.Option(
        "paper_export",
        "--output-dir", "-o",
        help="Output directory for LaTeX tables, plots, and figures",
    ),
    formats: str = typer.Option(
        "latex,plots",
        "--formats", "-f",
        help="Export formats: latex, plots, csv (comma-separated)",
    ),
) -> None:
    """Generate publication-grade LaTeX tables, plots, and figures.

    This command queries Postgres for experiment results and regenerates
    all paper assets in one go — ready for \\input{} inclusion in a
    LaTeX manuscript.

    Examples:
        # Export all experiments in a group
        python -m src.main paper-export --group gptq_ablation

        # Export specific experiment IDs
        python -m src.main paper-export -e 1,2,3,4,5 -o paper_export
    """
    _require_settings()
    from sqlalchemy import text

    from .db import Experiment, Metric, QuantConfig, get_session

    console.print("[bold blue]Paper Export — generating publication assets[/bold blue]")

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "tables").mkdir(exist_ok=True)
    (out / "figures").mkdir(exist_ok=True)

    session = get_session()

    # Resolve experiment IDs
    exp_ids: list[int] = []
    if experiment_ids:
        exp_ids = [int(x.strip()) for x in experiment_ids.split(",") if x.strip()]
    elif group:
        from .db.models import ExperimentGroup
        grp = session.query(ExperimentGroup).filter_by(name=group).first()
        if grp:
            exps = session.query(Experiment).filter_by(group_id=grp.id, status="completed").all()
            exp_ids = [e.id for e in exps]
        if not exp_ids:
            console.print(f"[yellow]No completed experiments in group '{group}'[/yellow]")
            session.close()
            return
    else:
        exps = session.query(Experiment).filter_by(status="completed").order_by(Experiment.id.desc()).limit(50).all()
        exp_ids = [e.id for e in exps]

    if not exp_ids:
        console.print("[yellow]No experiments found to export.[/yellow]")
        session.close()
        return

    console.print(f"Exporting {len(exp_ids)} experiment(s)...")

    fmt_list = [f.strip() for f in formats.split(",")]

    # ── Gather data ──────────────────────────────────────────────────
    import pandas as pd

    rows = []
    for eid in exp_ids:
        exp = session.query(Experiment).get(eid)
        if exp is None:
            continue
        metrics = session.query(Metric).filter_by(experiment_id=eid).all()
        qc = session.query(QuantConfig).filter_by(experiment_id=eid).first()
        for m in metrics:
            rows.append({
                "experiment_id": eid,
                "model": exp.model_name,
                "method": qc.method_name if qc else "baseline",
                "bit_width": qc.bit_width if qc else 16,
                "dataset": m.dataset,
                "metric": m.metric_name,
                "value": m.value,
            })

    if not rows:
        console.print("[yellow]No metrics found for the selected experiments.[/yellow]")
        session.close()
        return

    df = pd.DataFrame(rows)

    # ── LaTeX tables ─────────────────────────────────────────────────
    if "latex" in fmt_list:
        try:
            from .analytics.latex_export import export_metrics_table_enhanced

            for dataset in df["dataset"].unique():
                subset = df[df["dataset"] == dataset]
                tex = export_metrics_table_enhanced(
                    subset.to_dict("records"),
                    caption=f"Results on {dataset}",
                )
                tex_path = out / "tables" / f"{dataset}_results.tex"
                tex_path.write_text(tex)
                console.print(f"  [green]Table → {tex_path}[/green]")
        except Exception as e:
            console.print(f"  [red]LaTeX export failed: {e}[/red]")
            raise typer.Exit(1)

    # ── Plots ────────────────────────────────────────────────────────
    if "plots" in fmt_list:
        try:
            from .analytics.paper_plots import (
                plot_method_comparison_bar,
                plot_pareto_frontier,
            )
            from .analytics.pareto import ParetoPoint, compute_pareto_frontier

            # Method comparison bar chart
            pivot = df[df["metric"] == "perplexity"].groupby(["method", "dataset"])["value"].mean().reset_index()
            if not pivot.empty:
                fig = plot_method_comparison_bar(
                    methods=pivot["method"].unique().tolist(),
                    datasets=pivot["dataset"].unique().tolist(),
                    values={m: pivot[pivot["method"] == m]["value"].tolist() for m in pivot["method"].unique()},
                    metric_name="Perplexity",
                )
                fig_path = out / "figures" / "method_comparison.pdf"
                fig.savefig(str(fig_path), bbox_inches="tight")
                console.print(f"  [green]Plot → {fig_path}[/green]")

            # Pareto frontier (perplexity vs model size)
            # Requires hardware stats – best-effort
            try:
                from .db.models import HardwareBenchmark
                points = []
                for eid in exp_ids:
                    ppl = session.query(Metric).filter_by(
                        experiment_id=eid, metric_name="perplexity"
                    ).first()
                    hw = session.query(HardwareBenchmark).filter_by(experiment_id=eid).first()
                    if ppl and hw and hw.model_size_mb:
                        points.append(ParetoPoint(
                            x=hw.model_size_mb, y=ppl.value,
                            label=f"exp-{eid}",
                        ))
                if len(points) >= 2:
                    frontier = compute_pareto_frontier(points)
                    fig2 = plot_pareto_frontier(
                        frontier, x_label="Model Size (MB)", y_label="Perplexity",
                    )
                    fig2_path = out / "figures" / "pareto_frontier.pdf"
                    fig2.savefig(str(fig2_path), bbox_inches="tight")
                    console.print(f"  [green]Plot → {fig2_path}[/green]")
            except Exception as hw_err:
                console.print(f"  [yellow]Pareto frontier skipped (no hardware_stats data): {hw_err}[/yellow]")

        except Exception as e:
            console.print(f"  [red]Plot export failed: {e}[/red]")
            raise typer.Exit(1)

    # ── CSV dump ─────────────────────────────────────────────────────
    if "csv" in fmt_list:
        csv_path = out / "results.csv"
        df.to_csv(csv_path, index=False)
        console.print(f"  [green]CSV → {csv_path}[/green]")

    session.close()
    console.print(f"\n[bold green]Export complete → {out}/[/bold green]")


# ============================================================================
# Cross-Hardware Comparison Command
# ============================================================================


@app.command("cross-hardware")
def cross_hardware_cmd(
    hw_a: str = typer.Option(
        "NVIDIA",
        "--hw-a",
        help="Hardware label A (matches against gpu_type, e.g. 'NVIDIA')",
    ),
    hw_b: str = typer.Option(
        "AMD",
        "--hw-b",
        help="Hardware label B (matches against gpu_type, e.g. 'AMD')",
    ),
    metric: str = typer.Option(
        "perplexity",
        "--metric",
        help="Metric to compare (e.g. 'perplexity')",
    ),
    dataset: str = typer.Option(
        "wikitext2",
        "--dataset",
        help="Dataset to filter metrics on",
    ),
    output_dir: str = typer.Option(
        "reports/cross_hardware",
        "--output-dir", "-o",
        help="Directory for comparison plots and tables",
    ),
    export_latex: bool = typer.Option(
        False,
        "--export-latex/--no-latex",
        help="Export a LaTeX comparison table",
    ),
) -> None:
    """Compare experiment results across hardware backends (e.g. CUDA vs ROCm)."""
    _require_settings()
    from pathlib import Path
    from rich.table import Table

    from .analytics.cross_hardware import compare_hardware_results, plot_cross_hardware

    console.print(f"[bold blue]Cross-Hardware Comparison: {hw_a} vs {hw_b}[/bold blue]")
    console.print(f"Metric: {metric}, Dataset: {dataset}")

    comparisons = compare_hardware_results(
        hw_a=hw_a,
        hw_b=hw_b,
        metric_name=metric,
        dataset=dataset,
    )

    if not comparisons:
        console.print(
            f"[bold red]No matched experiments found for {hw_a} vs {hw_b}.[/bold red]\n"
            f"To generate cross-hardware comparisons, run the same experiment on both "
            f"hardware backends. Matching is by (model, method, bit_width)."
        )
        raise typer.Exit(1)

    # Rich table of results
    table = Table(title=f"Cross-Hardware Comparison ({hw_a} vs {hw_b})")
    table.add_column("Model", style="cyan")
    table.add_column("Method", style="magenta")
    table.add_column("Bits", justify="right")
    table.add_column(f"{hw_a} PPL", justify="right")
    table.add_column(f"{hw_b} PPL", justify="right")
    table.add_column("Δ PPL %", justify="right")

    for c in comparisons:
        delta_style = "green" if c.perplexity_delta < 0.01 else "yellow" if c.perplexity_delta < 0.05 else "red"
        table.add_row(
            c.model,
            c.method,
            str(c.bit_width),
            f"{c.hw_a_perplexity:.2f}",
            f"{c.hw_b_perplexity:.2f}",
            f"[{delta_style}]{c.perplexity_delta * 100:.2f}%[/{delta_style}]",
        )

    console.print(table)

    # Generate plots
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    plot_paths = plot_cross_hardware(comparisons, output_path=out / "cross_hardware_scatter")
    for p in plot_paths:
        console.print(f"  [green]Plot → {p}[/green]")

    # Optional LaTeX export
    if export_latex:
        from .analytics.latex_export import export_metrics_table_enhanced

        records = [c.to_dict() for c in comparisons]
        tex = export_metrics_table_enhanced(
            records,
            caption=f"Cross-Hardware Comparison: {hw_a} vs {hw_b}",
        )
        tex_path = out / "cross_hardware_table.tex"
        tex_path.write_text(tex)
        console.print(f"  [green]LaTeX → {tex_path}[/green]")

    console.print(f"\n[bold green]Comparison complete: {len(comparisons)} matched experiments[/bold green]")


# ============================================================================
# Version Command
# ============================================================================


@app.command("version")
def version_cmd() -> None:
    """Show version information."""
    from . import __version__
    
    console.print(f"LLM Quant Lab v{__version__}")
    console.print()
    console.print("A framework for LLM quantization experiments")
    console.print("Built on top of LightCompress/LLMC")


# ============================================================================
# Main Entry Point
# ============================================================================


def main() -> None:
    """Main entry point."""
    app()


if __name__ == "__main__":
    main()
