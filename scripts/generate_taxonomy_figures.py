"""
Generate academic figures for ASPLOS and Thesis papers.
Colors match the LLM-Quant-Lab frontend design system.
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
import numpy as np
import os

COLORS = {
    "hw":      "#0ea5e9",   # sky blue (charts)
    "hw_light":"#e0f2fe",
    "dt":      "#22c55e",   # green (success)
    "dt_light":"#f0fdf4",
    "sch":     "#c5a47e",   # gold accent
    "sch_light":"#faf6f0",
    "algo":    "#a855f7",   # purple (GPTQ chart)
    "algo_light":"#faf5ff",
    "bg":      "#ffffff",
    "text":    "#1a1a1a",
    "text2":   "#666666",
    "border":  "#e5e5e5",
    "danger":  "#ef4444",
    "amber":   "#f59e0b",
    "gray":    "#6b7280",
}

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Inter", "Helvetica Neue", "Arial", "sans-serif"],
    "font.size": 9,
    "axes.titlesize": 11,
    "axes.titleweight": "bold",
    "figure.facecolor": COLORS["bg"],
    "axes.facecolor": COLORS["bg"],
    "savefig.facecolor": COLORS["bg"],
    "savefig.bbox": "tight",
    "savefig.dpi": 300,
})

OUT_ASPLOS = "papers/asplos2027/figures"
OUT_THESIS = "papers/llm-quant-lab/figures"
OUT_IISWC = "papers/iiswc2026/figures"

os.makedirs(OUT_ASPLOS, exist_ok=True)
os.makedirs(OUT_THESIS, exist_ok=True)
os.makedirs(OUT_IISWC, exist_ok=True)


def save(fig, name):
    for d in [OUT_ASPLOS, OUT_THESIS, OUT_IISWC]:
        fig.savefig(os.path.join(d, f"{name}.pdf"), format="pdf")
        fig.savefig(os.path.join(d, f"{name}.png"), format="png")
    print(f"  saved {name}")


# ─────────────────────────────────────────────────────────────────────
# Figure 1: Quantization Taxonomy Overview
# ─────────────────────────────────────────────────────────────────────
def fig_taxonomy():
    fig, ax = plt.subplots(figsize=(14, 8.5))
    ax.set_xlim(0, 14)
    ax.set_ylim(0, 8.5)
    ax.axis("off")

    layers = [
        ("Hardware Platforms", 7.2, COLORS["hw"], COLORS["hw_light"],
         ["AMD MI300X\n(CDNA3)", "AMD MI210\n(CDNA2)", "NVIDIA H100\n(Hopper)",
          "NVIDIA A100\n(Ampere)", "NVIDIA B200\n(Blackwell)", "Apple M4", "Google\nTPU v5e"]),
        ("Native Data Types", 5.2, COLORS["dt"], COLORS["dt_light"],
         ["FP32", "FP16", "BF16", "TF32", "INT8", "INT4",
          "FP8\nE4M3", "FP8\nE5M2", "FP4\nE2M1", "FP6", "NF4", "MXFP8"]),
        ("Quantization Schemes", 3.2, COLORS["sch"], COLORS["sch_light"],
         ["W4", "W3", "W2", "A16W8", "Static\nA8W8", "Dynamic\nA8W8",
          "Dynamic\nA4W4", "FP8\nW8A8", "QLoRA\nNF4+FP16", "Mixed\n2:4 Sp."]),
        ("Algorithms", 1.2, COLORS["algo"], COLORS["algo_light"],
         ["GPTQ", "AWQ", "Smooth-\nQuant", "LLM\n.int8()", "RTN", "HQQ",
          "QuaRot", "SpQR", "Omni-\nQuant", "ParetoQ", "BitNet", "QLoRA"]),
    ]

    for title, y_base, color, bg_color, items in layers:
        n = len(items)
        total_w = min(13.0, n * 1.1)
        box_w = total_w / n - 0.08
        x_start = (14 - total_w) / 2

        ax.text(0.3, y_base + 0.65, title, fontsize=10, fontweight="bold",
                color=color, va="center")

        for i, label in enumerate(items):
            x = x_start + i * (total_w / n)
            rect = FancyBboxPatch((x, y_base), box_w, 0.9,
                                  boxstyle="round,pad=0.06",
                                  facecolor=bg_color, edgecolor=color,
                                  linewidth=1.2)
            ax.add_patch(rect)
            ax.text(x + box_w / 2, y_base + 0.45, label,
                    fontsize=7.5, ha="center", va="center",
                    color=COLORS["text"], fontweight="medium")

    arrow_kw = dict(arrowstyle="-|>", color=COLORS["gray"],
                    mutation_scale=10, lw=0.8)
    labels_drawn = set()
    for sx, sy, ex, ey, lbl in [
        (3.5, 7.2, 3.5, 6.4, "supports"),
        (7.0, 7.2, 7.0, 6.4, "supports"),
        (10.5, 7.2, 10.5, 6.4, "supports"),
        (3.5, 5.2, 3.5, 4.4, "uses"),
        (7.0, 5.2, 7.0, 4.4, "uses"),
        (10.5, 5.2, 10.5, 4.4, "uses"),
        (3.5, 2.1, 3.5, 3.2, "implements"),
        (7.0, 2.1, 7.0, 3.2, "implements"),
        (10.5, 2.1, 10.5, 3.2, "implements"),
    ]:
        ax.annotate("", xy=(ex, ey), xytext=(sx, sy),
                     arrowprops=arrow_kw)
        mid_y = (sy + ey) / 2
        if lbl not in labels_drawn:
            ax.text(sx + 0.15, mid_y, lbl, fontsize=6.5,
                    color=COLORS["gray"], fontstyle="italic", va="center")
            labels_drawn.add(lbl)

    legend_items = [
        mpatches.Patch(facecolor=COLORS["hw_light"], edgecolor=COLORS["hw"], label="Hardware"),
        mpatches.Patch(facecolor=COLORS["dt_light"], edgecolor=COLORS["dt"], label="Data Types"),
        mpatches.Patch(facecolor=COLORS["sch_light"], edgecolor=COLORS["sch"], label="Schemes"),
        mpatches.Patch(facecolor=COLORS["algo_light"], edgecolor=COLORS["algo"], label="Algorithms"),
    ]
    ax.legend(handles=legend_items, loc="upper right", fontsize=8,
              frameon=True, edgecolor=COLORS["border"], fancybox=True)

    fig.suptitle("LLM Quantization Taxonomy: Hardware > Data Types > Schemes > Algorithms",
                 fontsize=12, fontweight="bold", color=COLORS["text"], y=0.97)
    save(fig, "taxonomy_overview")
    plt.close(fig)


# ─────────────────────────────────────────────────────────────────────
# Figure 2: Hardware Precision Support Matrix
# ─────────────────────────────────────────────────────────────────────
# Module-level so per-venue renderers (e.g. scripts/generate_iiswc_fig2.py) can
# reuse the exact same support data without duplicating it.
HW_MATRIX_GPUS = [
    "AMD MI350\n(CDNA4)", "AMD MI300X\n(CDNA3)", "AMD MI210\n(CDNA2)",
    "AMD RX 7900 XTX", "NVIDIA B200\n(Blackwell)", "NVIDIA H100\n(Hopper)",
    "NVIDIA A100\n(Ampere)", "NVIDIA L40S", "NVIDIA RTX 4090",
]
HW_MATRIX_FORMATS = ["FP32", "FP16", "BF16", "TF32", "INT8", "INT4",
                     "FP8\nE4M3", "FP8\nE5M2", "FP4\nE2M1", "FP6",
                     "MXFP8", "MXFP4", "FP8\n2:4", "FP4\n2:4"]


# 2=native, 1=software dequant, 0=not supported.
# Sources: NVIDIA Ada (RTX 4090 / L40S) 4th-gen Tensor Cores add native FP8
# (E4M3/E5M2) and retain native INT4 (Turing/Ampere/Ada IMMA); Hopper (H100)
# dropped INT4 tensor ops (software only). NVIDIA structured 2:4 sparsity
# (Ampere+) accelerates the same dtypes as the dense path for that gen:
# sparse FP8 on Ada/Hopper/Blackwell, sparse FP4 on Blackwell only. AMD CDNA
# matrix cores do not expose NVIDIA-style 2:4 structured sparsity.
HW_MATRIX_DATA = np.array([
    #FP32 FP16 BF16 TF32 INT8 INT4 FP8a FP8b FP4  FP6  MX8  MX4  spFP8 spFP4
    [2,   2,   2,   0,   2,   1,   2,   2,   2,   2,   2,   2,   0,   0],   # MI350
    [2,   2,   2,   0,   2,   1,   2,   2,   0,   0,   0,   0,   0,   0],   # MI300X
    [2,   2,   2,   0,   2,   1,   0,   0,   0,   0,   0,   0,   0,   0],   # MI210
    [2,   2,   2,   0,   1,   1,   0,   0,   0,   0,   0,   0,   0,   0],   # RX 7900
    [2,   2,   2,   2,   2,   1,   2,   2,   2,   2,   2,   2,   2,   2],   # B200
    [2,   2,   2,   2,   2,   1,   2,   2,   0,   0,   0,   0,   2,   0],   # H100
    [2,   2,   2,   2,   2,   2,   0,   0,   0,   0,   0,   0,   0,   0],   # A100
    [2,   2,   2,   2,   2,   2,   2,   2,   0,   0,   0,   0,   2,   0],   # L40S  (Ada: native INT4 + FP8)
    [2,   2,   2,   2,   2,   2,   2,   2,   0,   0,   0,   0,   2,   0],   # RTX 4090 (Ada: native INT4 + FP8)
])


def fig_hw_matrix():
    gpus = HW_MATRIX_GPUS
    formats = HW_MATRIX_FORMATS

    data = HW_MATRIX_DATA

    cmap = matplotlib.colors.ListedColormap([
        "#f3f4f6",        # 0 = not supported (light gray)
        COLORS["amber"],  # 1 = software dequant (amber)
        COLORS["dt"],     # 2 = native (green)
    ])
    bounds = [-0.5, 0.5, 1.5, 2.5]
    norm = matplotlib.colors.BoundaryNorm(bounds, cmap.N)

    fig, ax = plt.subplots(figsize=(12, 6))
    im = ax.imshow(data, cmap=cmap, norm=norm, aspect="auto")

    ax.set_xticks(range(len(formats)))
    ax.set_xticklabels(formats, fontsize=7.5, fontweight="medium")
    ax.set_yticks(range(len(gpus)))
    ax.set_yticklabels(gpus, fontsize=7.5)
    ax.tick_params(top=True, bottom=False, labeltop=True, labelbottom=False)

    for i in range(len(gpus)):
        for j in range(len(formats)):
            v = data[i, j]
            sym = {2: "Y", 1: "~", 0: "-"}[v]
            c = "white" if v == 2 else (COLORS["text"] if v == 1 else "#9ca3af")
            ax.text(j, i, sym, ha="center", va="center",
                    fontsize=11, color=c, fontweight="bold")

    for edge in ["top", "bottom", "left", "right"]:
        ax.spines[edge].set_color(COLORS["border"])
    ax.set_xticks(np.arange(len(formats)) - 0.5, minor=True)
    ax.set_yticks(np.arange(len(gpus)) - 0.5, minor=True)
    ax.grid(which="minor", color=COLORS["border"], linewidth=0.5)
    ax.tick_params(which="minor", size=0)

    legend_items = [
        mpatches.Patch(facecolor=COLORS["dt"], label="Native tensor core support"),
        mpatches.Patch(facecolor=COLORS["amber"], label="Software dequantization"),
        mpatches.Patch(facecolor="#f3f4f6", edgecolor="#d1d5db", label="Not supported"),
    ]
    ax.legend(handles=legend_items, loc="upper center",
              bbox_to_anchor=(0.5, -0.08), ncol=3, fontsize=8,
              frameon=True, edgecolor=COLORS["border"])

    fig.suptitle("Native Precision Support Across GPU Architectures",
                 fontsize=12, fontweight="bold", color=COLORS["text"], y=0.98)
    fig.tight_layout(rect=[0, 0, 1, 0.95])
    save(fig, "hardware_precision_matrix")
    plt.close(fig)


# ─────────────────────────────────────────────────────────────────────
# Figure 3: Algorithm-Method Landscape
# ─────────────────────────────────────────────────────────────────────
def fig_algo_landscape():
    algos = [
        # (name, compression_x, complexity_y, scope, year)
        ("RTN",         2.5,  0.5, "weight",  2020),
        ("LLM.int8()",  2.0,  1.5, "w+a",     2022),
        ("HQQ",         5.0,  0.8, "weight",  2023),
        ("SmoothQuant", 2.0,  3.0, "w+a",     2023),
        ("GPTQ",        5.5,  3.5, "weight",  2023),
        ("AWQ",         5.5,  3.2, "weight",  2023),
        ("SpQR",        5.0,  4.0, "weight",  2023),
        ("QLoRA",       4.0,  2.5, "weight",  2023),
        ("SqueezeLLM",  4.5,  3.8, "weight",  2023),
        ("OmniQuant",   6.0,  5.0, "weight",  2023),
        ("QuIP#",       8.5,  5.5, "weight",  2024),
        ("AQLM",        8.0,  5.8, "weight",  2024),
        ("QuaRot",      8.0,  5.0, "w+a",     2024),
        ("ATOM",        8.0,  4.5, "w+a",     2024),
        ("QuiK",        8.0,  4.2, "w+a",     2024),
        ("ParetoQ",    10.0,  7.5, "qat",     2025),
        ("BitNet",     12.0,  8.0, "qat",     2024),
    ]

    scope_colors = {
        "weight": COLORS["hw"],
        "w+a":    COLORS["danger"],
        "qat":    COLORS["algo"],
    }

    fig, ax = plt.subplots(figsize=(10, 6.5))
    for name, cx, cy, scope, year in algos:
        size = 40 + (year - 2020) * 30
        ax.scatter(cx, cy, s=size, c=scope_colors[scope],
                   alpha=0.85, edgecolors="white", linewidth=0.8, zorder=3)
        offset_y = 0.35 if name not in ("AWQ", "ATOM", "QuiK") else -0.35
        offset_x = 0.0
        if name == "AWQ":
            offset_x = 0.5
        if name == "AQLM":
            offset_x = -0.6
        ax.annotate(name, (cx, cy), xytext=(offset_x, offset_y),
                    textcoords="offset fontsize",
                    fontsize=7.5, fontweight="medium", color=COLORS["text"],
                    ha="center", va="bottom" if offset_y > 0 else "top")

    ax.set_xlabel("Compression Ratio (×)", fontsize=10, fontweight="medium")
    ax.set_ylabel("Method Complexity", fontsize=10, fontweight="medium")
    ax.set_xlim(0.5, 14)
    ax.set_ylim(-0.2, 9)

    ytick_labels = ["Calibration-\nfree", "Simple\ncalib.", "Moderate\noptim.",
                    "Block-wise\noptim.", "Hessian-\nbased", "Learned\nparams",
                    "Multi-pass\noptim.", "Light\nQAT", "Full\nQAT"]
    ax.set_yticks(np.linspace(0, 8, 9))
    ax.set_yticklabels(ytick_labels, fontsize=6.5)

    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["bottom"].set_color(COLORS["border"])
    ax.spines["left"].set_color(COLORS["border"])
    ax.grid(True, alpha=0.3, color=COLORS["border"])

    legend_items = [
        plt.scatter([], [], s=80, c=COLORS["hw"], label="Weight-only PTQ"),
        plt.scatter([], [], s=80, c=COLORS["danger"], label="Weight+Activation PTQ"),
        plt.scatter([], [], s=80, c=COLORS["algo"], label="QAT"),
    ]
    size_legend = [
        plt.scatter([], [], s=40, c=COLORS["gray"], alpha=0.5, label="2020"),
        plt.scatter([], [], s=100, c=COLORS["gray"], alpha=0.5, label="2023"),
        plt.scatter([], [], s=190, c=COLORS["gray"], alpha=0.5, label="2025"),
    ]
    l1 = ax.legend(handles=legend_items, title="Scope", loc="upper left",
                   fontsize=7, title_fontsize=8, frameon=True,
                   edgecolor=COLORS["border"])
    ax.add_artist(l1)
    ax.legend(handles=size_legend, title="Year (size)", loc="lower right",
              fontsize=7, title_fontsize=8, frameon=True,
              edgecolor=COLORS["border"])

    fig.suptitle("LLM Quantization Algorithm Landscape",
                 fontsize=12, fontweight="bold", color=COLORS["text"], y=0.98)
    fig.tight_layout(rect=[0, 0, 1, 0.95])
    save(fig, "algorithm_landscape")
    plt.close(fig)


# ─────────────────────────────────────────────────────────────────────
# Figure 4: Cross-Hardware Quantization Pipeline
# ─────────────────────────────────────────────────────────────────────
def fig_cross_hw_pipeline():
    fig, ax = plt.subplots(figsize=(12, 5.5))
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 5.5)
    ax.axis("off")

    def box(x, y, w, h, label, color, bg, fs=9):
        rect = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.1",
                              facecolor=bg, edgecolor=color, linewidth=1.5)
        ax.add_patch(rect)
        ax.text(x + w/2, y + h/2, label, ha="center", va="center",
                fontsize=fs, color=COLORS["text"], fontweight="medium",
                wrap=True)

    box(0.2, 2.0, 2.0, 1.4, "INT4 Weight\nStorage\n(GPTQ / AWQ)", COLORS["algo"], COLORS["algo_light"])

    box(3.0, 2.0, 1.8, 1.4, "Dequant\nEngine", COLORS["gray"], "#f3f4f6")

    ax.annotate("", xy=(3.0, 2.7), xytext=(2.2, 2.7),
                arrowprops=dict(arrowstyle="-|>", color=COLORS["text"], lw=1.5))

    box(5.5, 4.0, 2.5, 1.0, "INT4 Tensor Core GEMM\n>> FP32 accumulator",
        COLORS["dt"], COLORS["dt_light"], fs=8.5)
    ax.annotate("", xy=(5.5, 4.5), xytext=(4.8, 3.4),
                arrowprops=dict(arrowstyle="-|>", color=COLORS["dt"], lw=1.5))
    ax.text(5.0, 3.9, "NVIDIA A100\n(native INT4)", fontsize=8,
            color=COLORS["dt"], fontweight="bold", ha="center")

    box(5.5, 2.0, 2.5, 1.0, "Dequant >> FP16\nFP16 Tensor Core GEMM",
        COLORS["amber"], "#fef3c7", fs=8.5)
    ax.annotate("", xy=(5.5, 2.5), xytext=(4.8, 2.7),
                arrowprops=dict(arrowstyle="-|>", color=COLORS["amber"], lw=1.5))
    ax.text(5.0, 1.7, "H100 / MI300X\n(SW dequant)", fontsize=8,
            color=COLORS["amber"], fontweight="bold", ha="center")

    box(5.5, 0.2, 2.5, 1.0, "Convert >> FP4/FP8\nFP4/FP8 Tensor Core GEMM",
        COLORS["hw"], COLORS["hw_light"], fs=8.5)
    ax.annotate("", xy=(5.5, 0.7), xytext=(4.8, 2.0),
                arrowprops=dict(arrowstyle="-|>", color=COLORS["hw"], lw=1.5))
    ax.text(5.0, 0.0, "B200 / MI350\n(next-gen native)", fontsize=8,
            color=COLORS["hw"], fontweight="bold", ha="center")

    for y_pos in [4.0, 2.0, 0.2]:
        box(8.8, y_pos, 1.5, 1.0, "Output\nTensor", "#e5e5e5", "#fafafa")
        ax.annotate("", xy=(8.8, y_pos + 0.5), xytext=(8.0, y_pos + 0.5),
                    arrowprops=dict(arrowstyle="-|>", color=COLORS["gray"], lw=1.2))

    ax.annotate(
        "Numerical divergence:\ncuBLAS vs hipBLAS dequant\nproduces different FP16 values\n= different inference outputs",
        xy=(4.0, 2.0), xytext=(1.5, 0.3),
        fontsize=8.5, color=COLORS["danger"], fontstyle="italic",
        arrowprops=dict(arrowstyle="->", color=COLORS["danger"],
                        connectionstyle="arc3,rad=0.2", lw=1),
        bbox=dict(boxstyle="round,pad=0.3", facecolor="#fef2f2",
                  edgecolor=COLORS["danger"], alpha=0.9),
    )

    fig.suptitle("Cross-Hardware INT4 Inference Pipeline: Same Weights, Different Compute Paths",
                 fontsize=12, fontweight="bold", color=COLORS["text"], y=0.98)
    fig.tight_layout(rect=[0, 0, 1, 0.95])
    save(fig, "cross_hw_pipeline")
    plt.close(fig)


# ─────────────────────────────────────────────────────────────────────
# Figure 5: MoE Quantization Failure Mechanism
# ─────────────────────────────────────────────────────────────────────
def fig_moe_failure():
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 6))

    for ax in (ax1, ax2):
        ax.set_xlim(0, 6)
        ax.set_ylim(0, 8)
        ax.axis("off")

    def draw_box(ax, x, y, w, h, label, color, bg, fs=9):
        rect = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.08",
                              facecolor=bg, edgecolor=color, linewidth=1.3)
        ax.add_patch(rect)
        ax.text(x + w/2, y + h/2, label, ha="center", va="center",
                fontsize=fs, color=COLORS["text"], fontweight="medium")

    def arrow(ax, x1, y1, x2, y2, color=COLORS["gray"]):
        ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                    arrowprops=dict(arrowstyle="-|>", color=color, lw=1.3))

    ax1.text(3, 7.7, "Dense Transformer", fontsize=12, fontweight="bold",
             ha="center", color=COLORS["dt"])
    draw_box(ax1, 1.5, 6.5, 3, 0.8, "Input X", COLORS["border"], "#fafafa")
    arrow(ax1, 3, 6.5, 3, 6.0)
    draw_box(ax1, 0.8, 5.0, 4.4, 0.9,
             "SmoothQuant Scaling\nX' = X · diag(s)⁻¹", COLORS["hw"], COLORS["hw_light"])
    arrow(ax1, 3, 5.0, 3, 4.5)
    draw_box(ax1, 1.0, 3.3, 4.0, 1.0,
             "Attention + FFN Block\n(single path)", COLORS["dt"], COLORS["dt_light"])
    arrow(ax1, 3, 3.3, 3, 2.8)
    draw_box(ax1, 1.5, 1.8, 3, 0.8, "Output Y", COLORS["border"], "#fafafa")

    ax1.text(3, 1.2, "[OK]  PPL: 5.96 (expected: 5.96)", fontsize=10,
             ha="center", fontweight="bold", color=COLORS["dt"])
    ax1.text(3, 0.6, "Uniform scaling preserves\nlayer-internal relationships",
             fontsize=9, ha="center", color=COLORS["text2"], fontstyle="italic")

    ax2.text(3, 7.7, "MoE Transformer", fontsize=12, fontweight="bold",
             ha="center", color=COLORS["danger"])
    draw_box(ax2, 1.5, 6.5, 3, 0.8, "Input X", COLORS["border"], "#fafafa")
    arrow(ax2, 3, 6.5, 3, 6.0)
    draw_box(ax2, 0.8, 5.0, 4.4, 0.9,
             "SmoothQuant Scaling\nX' = X · diag(s)⁻¹", COLORS["hw"], COLORS["hw_light"])
    arrow(ax2, 3, 5.0, 3, 4.5)

    draw_box(ax2, 0.5, 3.5, 5.0, 0.9,
             "Gating Network G(X')\nTopK(Softmax(X'·W_g))",
             COLORS["danger"], "#fef2f2", fs=9.5)

    arrow(ax2, 1.5, 3.5, 1.0, 3.0)
    arrow(ax2, 3.0, 3.5, 3.0, 3.0)
    arrow(ax2, 4.5, 3.5, 5.0, 3.0)
    draw_box(ax2, 0.2, 2.2, 1.5, 0.7, "Expert 1", COLORS["sch"], COLORS["sch_light"], fs=8.5)
    draw_box(ax2, 2.2, 2.2, 1.5, 0.7, "Expert 2", COLORS["sch"], COLORS["sch_light"], fs=8.5)
    draw_box(ax2, 4.2, 2.2, 1.5, 0.7, "Expert N", COLORS["sch"], COLORS["sch_light"], fs=8.5)
    ax2.text(3.85, 2.55, "…", fontsize=16, ha="center", va="center", color=COLORS["text2"])

    arrow(ax2, 1.0, 2.2, 3.0, 1.8)
    arrow(ax2, 3.0, 2.2, 3.0, 1.8)
    arrow(ax2, 5.0, 2.2, 3.0, 1.8)
    draw_box(ax2, 1.5, 1.0, 3, 0.7, "Output Y", COLORS["border"], "#fafafa")

    ax2.text(3, 0.4, "[FAIL]  PPL: 4,805,887 (expected: 3.89)", fontsize=10,
             ha="center", fontweight="bold", color=COLORS["danger"])

    ax2.annotate(
        "Uniform s (across ALL experts)\ndistorts gating magnitudes\n>> wrong expert selection\n>> cascading OOD errors",
        xy=(3.0, 3.9), xytext=(0.5, 5.6),
        fontsize=8.5, color=COLORS["danger"],
        arrowprops=dict(arrowstyle="->", color=COLORS["danger"], lw=1.2),
        bbox=dict(boxstyle="round,pad=0.3", facecolor="#fef2f2",
                  edgecolor=COLORS["danger"]),
    )

    fig.suptitle("SmoothQuant on Dense vs. MoE Architectures: Gating Disruption Mechanism",
                 fontsize=12, fontweight="bold", color=COLORS["text"], y=0.98)
    fig.tight_layout(rect=[0, 0, 1, 0.94])
    save(fig, "moe_failure_mechanism")
    plt.close(fig)


if __name__ == "__main__":
    print("Generating taxonomy figures...")
    fig_taxonomy()
    fig_hw_matrix()
    fig_algo_landscape()
    fig_cross_hw_pipeline()
    fig_moe_failure()
    print("Done — all figures saved to both paper directories.")
