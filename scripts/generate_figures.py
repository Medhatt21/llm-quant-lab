#!/usr/bin/env python3
"""Generate publication-quality figures for both papers from reproduction_results.csv."""

import re
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import numpy as np
import pandas as pd
import seaborn as sns
from scipy.optimize import curve_fit

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CSV_PATH = PROJECT_ROOT / "reproduction_results.csv"

ASPLOS_FIG = PROJECT_ROOT / "papers" / "asplos2027" / "figures"
THESIS_FIG = PROJECT_ROOT / "papers" / "llm-quant-lab" / "figures"
ASPLOS_FIG.mkdir(parents=True, exist_ok=True)
THESIS_FIG.mkdir(parents=True, exist_ok=True)

plt.rcParams.update({
    "font.family": "serif",
    "font.size": 9,
    "axes.labelsize": 10,
    "axes.titlesize": 11,
    "legend.fontsize": 8,
    "xtick.labelsize": 8,
    "ytick.labelsize": 8,
    "figure.dpi": 300,
    "savefig.dpi": 300,
    "savefig.bbox": "tight",
    "savefig.pad_inches": 0.05,
})

MODEL_PARAMS = {
    "facebook/opt-125m": 0.125, "facebook/opt-350m": 0.35,
    "facebook/opt-1.3b": 1.3, "facebook/opt-2.7b": 2.7,
    "facebook/opt-6.7b": 6.7, "facebook/opt-13b": 13,
    "facebook/opt-30b": 30, "facebook/opt-66b": 66,
    "facebook/opt-iml-30b": 30,
    "bigscience/bloom-560m": 0.56, "bigscience/bloom-1b1": 1.1,
    "bigscience/bloom-1b7": 1.7, "bigscience/bloom-3b": 3,
    "bigscience/bloom-7b1": 7.1,
    "huggyllama/llama-7b": 7, "huggyllama/llama-13b": 13,
    "huggyllama/llama-30b": 30, "huggyllama/llama-65b": 65,
    "meta-llama/Llama-2-7b-hf": 7, "meta-llama/Llama-2-13b-hf": 13,
    "meta-llama/Llama-2-70b-hf": 70, "meta-llama/Llama-3.1-8B": 8,
    "mistralai/Mistral-7B-v0.1": 7, "mistralai/Mistral-7B-Instruct-v0.2": 7,
    "mistralai/Mixtral-8x7B-v0.1": 46.7,
    "mistralai/Mixtral-8x7B-Instruct-v0.1": 46.7,
}

MODEL_FAMILY = {}
for m in MODEL_PARAMS:
    if "opt" in m.lower():
        MODEL_FAMILY[m] = "OPT"
    elif "bloom" in m.lower():
        MODEL_FAMILY[m] = "BLOOM"
    elif "llama-2" in m.lower() or "Llama-2" in m:
        MODEL_FAMILY[m] = "Llama-2"
    elif "llama-3" in m.lower() or "Llama-3" in m:
        MODEL_FAMILY[m] = "Llama-3"
    elif "llama" in m.lower():
        MODEL_FAMILY[m] = "LLaMA"
    elif "mixtral" in m.lower():
        MODEL_FAMILY[m] = "Mixtral"
    elif "mistral" in m.lower():
        MODEL_FAMILY[m] = "Mistral"
    else:
        MODEL_FAMILY[m] = "Other"

VERDICT_COLORS = {
    "matching": "#2ecc71",
    "close": "#f39c12",
    "better": "#3498db",
    "worse": "#e74c3c",
    "no_paper_ref": "#bdc3c7",
}


def load_data() -> pd.DataFrame:
    df = pd.read_csv(CSV_PATH)
    df["params_b"] = df["model"].map(MODEL_PARAMS)
    df["family"] = df["model"].map(MODEL_FAMILY)
    return df


# ── Figure 1: Paper vs AMD Scatter Plot ──────────────────────────────────────

def fig_scatter_paper_vs_amd(df: pd.DataFrame):
    has_paper = df[df["paper_value"].notna() & df["amd_value"].notna()].copy()
    has_paper = has_paper[has_paper["amd_value"] < 100]  # exclude Mixtral catastrophe

    fig, ax = plt.subplots(figsize=(3.5, 3.5))

    for verdict, color in VERDICT_COLORS.items():
        mask = has_paper["amd_verdict"] == verdict
        if mask.sum() == 0:
            continue
        ax.scatter(
            has_paper.loc[mask, "paper_value"],
            has_paper.loc[mask, "amd_value"],
            c=color, s=18, alpha=0.8, edgecolors="k", linewidths=0.3,
            label=verdict.capitalize(), zorder=3,
        )

    lo = min(has_paper["paper_value"].min(), has_paper["amd_value"].min()) * 0.9
    hi = max(has_paper["paper_value"].max(), has_paper["amd_value"].max()) * 1.05
    ax.plot([lo, hi], [lo, hi], "k--", lw=0.7, alpha=0.5, label="y = x")
    ax.set_xlim(lo, hi)
    ax.set_ylim(lo, hi)
    ax.set_xlabel("Published (NVIDIA) Value")
    ax.set_ylabel("AMD ROCm Value")
    ax.set_title("Reproduction Fidelity: AMD vs Published")
    ax.legend(loc="upper left", framealpha=0.9)
    ax.set_aspect("equal")

    for dest in [ASPLOS_FIG, THESIS_FIG]:
        fig.savefig(dest / "scatter_paper_vs_amd.pdf")
        fig.savefig(dest / "scatter_paper_vs_amd.png")
    plt.close(fig)
    print("  scatter_paper_vs_amd")


# ── Figure 2: Scaling Curve ──────────────────────────────────────────────────

def fig_scaling_curve(df: pd.DataFrame):
    ppl = df[(df["metric"] == "perplexity") & (df["dataset"] == "wikitext2")].copy()
    has_ref = ppl[ppl["paper_value"].notna() & ppl["amd_value"].notna()].copy()
    has_ref = has_ref[has_ref["method"] != "fp16"]
    has_ref["abs_bias"] = has_ref["amd_diff_pct"].abs()
    has_ref = has_ref[has_ref["abs_bias"] < 100]
    has_ref = has_ref.dropna(subset=["params_b", "abs_bias"])

    fig, ax = plt.subplots(figsize=(4.5, 3))

    method_styles = {
        "gptq": ("o", "#2c3e50", "GPTQ"),
        "awq": ("s", "#e74c3c", "AWQ"),
        "smoothquant": ("^", "#3498db", "SmoothQuant"),
        "llmint8": ("D", "#9b59b6", "LLM.int8()"),
        "rtn": ("v", "#f39c12", "RTN"),
    }
    for method, (marker, color, label) in method_styles.items():
        sub = has_ref[has_ref["method"] == method]
        if len(sub) == 0:
            continue
        ax.scatter(sub["params_b"], sub["abs_bias"], marker=marker, c=color,
                   s=20, alpha=0.7, edgecolors="k", linewidths=0.3, label=label, zorder=3)

    valid = has_ref[has_ref["abs_bias"] > 0]
    if len(valid) > 3:
        try:
            def power_law(x, a, b):
                return a * np.power(x, b)
            popt, _ = curve_fit(power_law, valid["params_b"].values, valid["abs_bias"].values,
                                p0=[0.42, -0.089], maxfev=5000)
            x_fit = np.logspace(np.log10(valid["params_b"].min()), np.log10(valid["params_b"].max()), 100)
            ax.plot(x_fit, power_law(x_fit, *popt), "k--", linewidth=1.2, alpha=0.7,
                    label=f"Fit: $|\\delta| = {popt[0]:.2f} \\cdot N^{{{popt[1]:.3f}}}$")
        except RuntimeError:
            pass

    ax.set_xscale("log")
    ax.set_xlabel("Model Parameters (Billions)")
    ax.set_ylabel("|Bias| from Paper (%)")
    ax.set_title("Cross-Hardware Degradation vs Model Scale")
    ax.legend(loc="upper right", framealpha=0.9, fontsize=6.5)
    ax.xaxis.set_major_formatter(ticker.FuncFormatter(lambda x, _: f"{x:.1f}B" if x < 1 else f"{x:.0f}B"))

    for dest in [ASPLOS_FIG, THESIS_FIG]:
        fig.savefig(dest / "scaling_curve.pdf")
        fig.savefig(dest / "scaling_curve.png")
    plt.close(fig)
    print("  scaling_curve")


# ── Figure 3: Verdict Distribution Bar Chart ─────────────────────────────────

def fig_verdict_distribution(df: pd.DataFrame):
    has_paper = df[df["amd_verdict"] != "no_paper_ref"].copy()

    method_order = ["gptq", "awq", "smoothquant", "llmint8", "rtn"]
    method_labels = {
        "gptq": "GPTQ", "awq": "AWQ", "smoothquant": "SmoothQuant",
        "llmint8": "LLM.int8()", "rtn": "RTN",
    }
    verdicts = ["matching", "close", "better", "worse"]
    verdict_labels = ["Match", "Close", "Better", "Worse"]

    counts = {}
    labels = []
    for method in method_order:
        sub = has_paper[has_paper["method"] == method]
        if len(sub) == 0:
            continue
        lbl = method_labels.get(method, method.upper())
        counts[lbl] = {v: (sub["amd_verdict"] == v).sum() for v in verdicts}
        labels.append(lbl)

    if not counts:
        return

    fig, ax = plt.subplots(figsize=(4.5, 2.8))
    x = np.arange(len(labels))
    width = 0.55
    bottom = np.zeros(len(labels))

    for verdict, vlabel in zip(verdicts, verdict_labels):
        vals = np.array([counts[m].get(verdict, 0) for m in labels])
        ax.bar(x, vals, width, bottom=bottom, label=vlabel,
               color=VERDICT_COLORS[verdict], edgecolor="white", linewidth=0.5)
        for i, v in enumerate(vals):
            if v > 0:
                ax.text(i, bottom[i] + v / 2, str(v), ha="center", va="center",
                        fontsize=7, fontweight="bold", color="white" if verdict != "close" else "black")
        bottom += vals

    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=20, ha="right", fontsize=8)
    ax.set_ylabel("Number of Experiments")
    ax.set_title("Verdict Distribution by Quantization Method")
    ax.legend(framealpha=0.9, fontsize=7, loc="upper right")
    ax.set_xlim(-0.5, len(labels) - 0.5)

    for dest in [ASPLOS_FIG, THESIS_FIG]:
        fig.savefig(dest / "verdict_distribution.pdf")
        fig.savefig(dest / "verdict_distribution.png")
    plt.close(fig)
    print("  verdict_distribution")


# ── Figure 4: Method Bias Box Plot ───────────────────────────────────────────

def fig_method_bias_boxplot(df: pd.DataFrame):
    has_paper = df[df["paper_value"].notna() & df["amd_diff_pct"].notna()].copy()
    has_paper = has_paper[has_paper["amd_diff_pct"].abs() < 100]

    fig, ax = plt.subplots(figsize=(4.5, 2.8))
    
    method_order = ["fp16", "gptq", "awq", "llmint8", "smoothquant", "rtn"]
    short_labels = {"fp16": "FP16", "gptq": "GPTQ", "awq": "AWQ",
                    "llmint8": "INT8", "smoothquant": "SQ", "rtn": "RTN"}
    plot_data = []
    labels = []
    for m in method_order:
        sub = has_paper[has_paper["method"] == m]["amd_diff_pct"]
        if len(sub) > 0:
            plot_data.append(sub.values)
            labels.append(short_labels.get(m, m.upper()))

    bp = ax.boxplot(plot_data, tick_labels=labels, patch_artist=True, widths=0.5,
                    medianprops=dict(color="black", linewidth=1.5))
    
    colors = ["#95a5a6", "#2c3e50", "#e74c3c", "#9b59b6", "#3498db", "#f39c12"]
    for patch, color in zip(bp["boxes"], colors[:len(plot_data)]):
        patch.set_facecolor(color)
        patch.set_alpha(0.6)

    ax.axhline(y=0, color="gray", linestyle=":", linewidth=0.7)
    ax.set_ylabel("% Difference from Paper")
    ax.set_title("Hardware Bias by Quantization Method")

    for dest in [ASPLOS_FIG, THESIS_FIG]:
        fig.savefig(dest / "method_bias_boxplot.pdf")
        fig.savefig(dest / "method_bias_boxplot.png")
    plt.close(fig)
    print("  method_bias_boxplot")


# ── Figure 5: Architecture Robustness Heatmap ────────────────────────────────

def fig_architecture_heatmap(df: pd.DataFrame):
    has_paper = df[df["amd_verdict"] != "no_paper_ref"].copy()

    families = ["OPT", "BLOOM", "LLaMA", "Llama-2", "Mistral", "Mixtral"]
    methods = ["gptq", "awq", "smoothquant", "llmint8", "rtn"]
    method_labels = {"gptq": "GPTQ", "awq": "AWQ", "smoothquant": "SmoothQuant",
                     "llmint8": "LLM.int8()", "rtn": "RTN"}

    matrix = np.full((len(families), len(methods)), np.nan)

    for i, fam in enumerate(families):
        for j, meth in enumerate(methods):
            sub = has_paper[(has_paper["family"] == fam) & (has_paper["method"] == meth)]
            if len(sub) > 0:
                match_rate = (sub["amd_verdict"] == "matching").mean() * 100
                matrix[i, j] = match_rate

    fig, ax = plt.subplots(figsize=(4.5, 3))

    cmap = sns.color_palette("RdYlGn", as_cmap=True)
    im = ax.imshow(matrix, cmap=cmap, vmin=0, vmax=100, aspect="auto")

    ax.set_xticks(range(len(methods)))
    ax.set_xticklabels([method_labels[m] for m in methods], rotation=35, ha="right", fontsize=7)
    ax.set_yticks(range(len(families)))
    ax.set_yticklabels(families)

    for i in range(len(families)):
        for j in range(len(methods)):
            val = matrix[i, j]
            if np.isnan(val):
                ax.text(j, i, "N/A", ha="center", va="center", fontsize=6.5, color="#9ca3af")
            else:
                color = "white" if val < 50 else "black"
                ax.text(j, i, f"{val:.0f}%", ha="center", va="center", fontsize=7.5,
                        fontweight="bold", color=color)

    cbar = fig.colorbar(im, ax=ax, shrink=0.8)
    cbar.set_label("Match Rate (%)")
    ax.set_title("Reproduction Success by Architecture & Method")

    for dest in [ASPLOS_FIG, THESIS_FIG]:
        fig.savefig(dest / "architecture_heatmap.pdf")
        fig.savefig(dest / "architecture_heatmap.png")
    plt.close(fig)
    print("  architecture_heatmap")


# ── Figure 6: Bit-Width Degradation ──────────────────────────────────────────

def fig_bitwidth_degradation(df: pd.DataFrame):
    ppl = df[(df["metric"] == "perplexity") & (df["dataset"] == "wikitext2")].copy()
    fp16 = ppl[ppl["method"] == "fp16"].set_index("model")["amd_value"].to_dict()

    fig, ax = plt.subplots(figsize=(3.5, 3))

    for model_pattern, label, color in [
        ("facebook/opt-2.7b", "OPT-2.7B", "#2c3e50"),
        ("facebook/opt-6.7b", "OPT-6.7B", "#e74c3c"),
        ("meta-llama/Llama-2-7b-hf", "Llama-2-7B", "#3498db"),
    ]:
        sub = ppl[(ppl["model"] == model_pattern) & (ppl["method"].isin(["gptq", "awq"]))].copy()
        if model_pattern not in fp16:
            continue
        sub["degradation"] = sub["amd_value"] / fp16[model_pattern]
        sub = sub.sort_values("bit_width")
        
        if len(sub) == 0:
            continue

        bits = [16] + sub["bit_width"].tolist()
        degs = [1.0] + sub["degradation"].tolist()
        
        ax.plot(bits, degs, "o-", color=color, markersize=5, linewidth=1.2, label=label)

    ax.set_xlabel("Bit Width")
    ax.set_ylabel("Perplexity Ratio (Quantized / FP16)")
    ax.set_title("Degradation vs Bit Width")
    ax.set_xticks([3, 4, 8, 16])
    ax.legend(framealpha=0.9)
    ax.axhline(y=1.0, color="gray", linestyle=":", linewidth=0.7)

    for dest in [ASPLOS_FIG, THESIS_FIG]:
        fig.savefig(dest / "bitwidth_degradation.pdf")
        fig.savefig(dest / "bitwidth_degradation.png")
    plt.close(fig)
    print("  bitwidth_degradation")


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    print("Generating publication figures...")
    df = load_data()
    print(f"Loaded {len(df)} rows")

    fig_scatter_paper_vs_amd(df)
    fig_scaling_curve(df)
    fig_verdict_distribution(df)
    fig_method_bias_boxplot(df)
    fig_architecture_heatmap(df)
    fig_bitwidth_degradation(df)

    print(f"\nFigures saved to:")
    print(f"  ASPLOS: {ASPLOS_FIG}")
    print(f"  Thesis: {THESIS_FIG}")
    print("Done.")


if __name__ == "__main__":
    main()
