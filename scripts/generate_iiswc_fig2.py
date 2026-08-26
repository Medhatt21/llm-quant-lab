"""Render the IISWC Figure 2 precision-support matrix at page-width scale.

The shared renderer in generate_taxonomy_figures.py targets a single column, so
its 7.5 pt labels land at ~4 pt once LaTeX scales the figure down. This version
reuses the exact same support data (imported, not copied) and sizes the type for
a two-column ``figure*`` at \\textwidth: every font is set so that it lands
between 7 and 9 pt on the printed page.

    uv run --python .analysis-venv python scripts/generate_iiswc_fig2.py
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.colors
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np

from generate_taxonomy_figures import (
    COLORS,
    HW_MATRIX_DATA,
    HW_MATRIX_FORMATS,
    HW_MATRIX_GPUS,
    OUT_IISWC,
)

# Figure is drawn at FIG_W inches and placed at \textwidth (~7.0 in), so every
# font size below is divided by this factor on paper.
FIG_W, FIG_H = 14.0, 4.9
SCALE = FIG_W / 7.0  # 2.0

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Inter", "Helvetica Neue", "Arial", "sans-serif"],
    "figure.facecolor": "#ffffff",
    "axes.facecolor": "#ffffff",
    "savefig.facecolor": "#ffffff",
    "savefig.bbox": "tight",
    "savefig.dpi": 300,
})


def main() -> None:
    gpus, formats, data = HW_MATRIX_GPUS, HW_MATRIX_FORMATS, HW_MATRIX_DATA

    cmap = matplotlib.colors.ListedColormap([
        "#f3f4f6",        # 0 = not supported
        COLORS["amber"],  # 1 = software dequantization
        COLORS["dt"],     # 2 = native tensor-core support
    ])
    norm = matplotlib.colors.BoundaryNorm([-0.5, 0.5, 1.5, 2.5], cmap.N)

    fig, ax = plt.subplots(figsize=(FIG_W, FIG_H))
    ax.imshow(data, cmap=cmap, norm=norm, aspect="auto")

    ax.set_xticks(range(len(formats)))
    ax.set_xticklabels(formats, fontsize=8.0 * SCALE, fontweight="bold")
    ax.set_yticks(range(len(gpus)))
    ax.set_yticklabels(gpus, fontsize=8.0 * SCALE, fontweight="bold")
    ax.tick_params(top=True, bottom=False, labeltop=True, labelbottom=False,
                   length=0, pad=4)

    for i in range(len(gpus)):
        for j in range(len(formats)):
            v = data[i, j]
            sym = {2: "Y", 1: "~", 0: "–"}[v]
            colour = "white" if v == 2 else (COLORS["text"] if v == 1 else "#9ca3af")
            ax.text(j, i, sym, ha="center", va="center",
                    fontsize=9.0 * SCALE, color=colour, fontweight="bold")

    for edge in ["top", "bottom", "left", "right"]:
        ax.spines[edge].set_color(COLORS["border"])
    ax.set_xticks(np.arange(len(formats)) - 0.5, minor=True)
    ax.set_yticks(np.arange(len(gpus)) - 0.5, minor=True)
    ax.grid(which="minor", color="#ffffff", linewidth=1.6)
    ax.tick_params(which="minor", size=0)

    legend_items = [
        mpatches.Patch(facecolor=COLORS["dt"], label="Native tensor core (Y)"),
        mpatches.Patch(facecolor=COLORS["amber"], label="Software dequantization (~)"),
        mpatches.Patch(facecolor="#f3f4f6", edgecolor="#d1d5db", label="Not supported (–)"),
    ]
    ax.legend(handles=legend_items, loc="upper center",
              bbox_to_anchor=(0.5, -0.03), ncol=3, fontsize=7.5 * SCALE,
              frameon=False, handlelength=1.6, columnspacing=2.4)

    fig.tight_layout()
    for ext in ("pdf", "png"):
        out = f"{OUT_IISWC}/hardware_precision_matrix_wide.{ext}"
        fig.savefig(out, format=ext)
        print(f"  saved {out}")
    plt.close(fig)


if __name__ == "__main__":
    main()
