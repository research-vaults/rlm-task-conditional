#!/usr/bin/env python3
"""Build the submission decision-boundary figure from frozen evidence files."""

from __future__ import annotations

import csv
import json
from pathlib import Path
import subprocess

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.lines import Line2D


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "paper" / "fig_task_comparison_submission"
LENGTH_TABLE = ROOT / "results" / "oolong_standard_multilength_n120_threeway_length_table_20260713.csv"
SEED20_ANALYSIS = ROOT / "results" / "browsecomp_plus_shard1_equal_cap_n45" / "semantic_equal_cap_n45_primary_analysis.json"
SEED21_ANALYSIS = ROOT / "results" / "browsecomp_plus_shard1_equal_cap_n45_seed21" / "semantic_equal_cap_n45_seed21_primary_analysis.json"

# Matplotlib's ordinary PDF text path embeds TrueType as CID/Identity-H, which
# AAAI-27 forbids even inside figures. The local TeX backend instead emits the
# same embedded Type 1 font class used by the manuscript.
#
# The canvas is authored at exactly \textwidth (7.0in), so \includegraphics
# applies no scaling and every nominal point size below is also the on-page
# point size. The previous 7.2in canvas was scaled by 0.9722, which silently
# reduced the 9.0pt annotations to 8.75pt.
mpl.rcParams.update(
    {
        "text.usetex": True,
        "font.family": "sans-serif",
        "font.sans-serif": ["Helvetica"],
        "font.size": 9.5,
        "axes.labelsize": 9.5,
        "axes.titlesize": 10.0,
        "xtick.labelsize": 9.5,
        "ytick.labelsize": 9.5,
        "legend.fontsize": 9.5,
    }
)

BROWSE_LABELS = ["RLM", "Iterative", "Text", "BM25"]
BROWSE_METHODS = [
    "standard_rlm_qwen36",
    "iterative_search_qwen36",
    "text_decompose_qwen36",
    "bm25_qwen36",
]

BLUE = "#4C78A8"
BLUE_EDGE = "#2F4F73"
GOLD = "#F2B447"
GOLD_EDGE = "#A76700"
GREEN = "#59A14F"
GREEN_EDGE = "#2D6A28"
GRAY = "#9C9C9C"
GRAY_EDGE = "#5E5E5E"


def load_length_rates() -> tuple[list[str], dict[str, np.ndarray]]:
    rows = list(csv.DictReader(LENGTH_TABLE.open(encoding="utf-8")))
    lengths = [8192, 16384, 32768, 65536, 131072]
    methods = ["slm_qparsed_typed", "standard_rlm", "direct_controller"]
    by_key = {(int(row["context_len"]), row["method"]): row for row in rows}
    expected = {(length, method) for length in lengths for method in methods}
    if set(by_key) != expected:
        raise ValueError(f"Unexpected length-table surface in {LENGTH_TABLE}")
    if any(int(by_key[(length, method)]["n"]) != 24 for length in lengths for method in methods):
        raise ValueError("Every plotted Oolong length/method cell must contain 24 rows")
    rates = {
        method: np.array([100.0 * float(by_key[(length, method)]["exact_rate"]) for length in lengths])
        for method in methods
    }
    return ["8k", "16k", "32k", "65k", "131k"], rates


def load_browse_rollout(path: Path, cost_key: str) -> dict[str, np.ndarray]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload["planned_n"] != 45 or payload["attempted_n"] != 45:
        raise ValueError(f"BrowseComp rollout is not the fixed N=45 endpoint: {path}")
    methods = payload["methods"]
    if any(method not in methods for method in BROWSE_METHODS):
        raise ValueError(f"BrowseComp rollout is missing a plotted route: {path}")

    accuracy = np.array([100.0 * methods[method]["semantic_accuracy"] for method in BROWSE_METHODS])
    intervals = np.array([methods[method]["wilson_95"] for method in BROWSE_METHODS], dtype=float) * 100.0
    return {
        "accuracy": accuracy,
        "cost": np.array([methods[method][cost_key] for method in BROWSE_METHODS]),
        "calls": np.array([methods[method]["model_calls_total"] for method in BROWSE_METHODS]),
        "error": np.vstack([accuracy - intervals[:, 0], intervals[:, 1] - accuracy]),
    }


def style_axis(ax: plt.Axes, upper: float = 105) -> None:
    ax.set_ylim(0, upper)
    # Explicit string labels keep the numerals in the figure's sans family. The
    # default formatter routes them through TeX math mode, which set them in
    # Computer Modern serif and clashed with every other label in the panel.
    ax.set_yticks(np.arange(0, 101, 20), [str(v) for v in range(0, 101, 20)])
    ax.grid(axis="y", color="#D7D7D7", linewidth=0.7)
    ax.set_axisbelow(True)
    ax.spines[["top", "right"]].set_visible(False)


def main() -> None:
    # Designed at approximately final AAAI two-column width. All plotted text
    # remains at least nine points after the small 7.2in -> textwidth scaling.
    fig, (left, right) = plt.subplots(
        1,
        2,
        figsize=(7.0, 1.78),
        # Panel (b) carries four inline labels in a log-scaled span; at 1.45:1.0
        # they had under 1.4pt of clearance from the whiskers. Panel (a) is a
        # five-point line chart and gives the width up without crowding.
        gridspec_kw={"width_ratios": [1.18, 1.0], "wspace": 0.22},
        constrained_layout=True,
    )

    length_labels, length_rates = load_length_rates()
    x = np.arange(len(length_labels))
    left.plot(x, length_rates["slm_qparsed_typed"], color=BLUE, marker="o", linewidth=1.8, markersize=4.5, label="SLM+typed")
    left.plot(x, length_rates["standard_rlm"], color=GOLD_EDGE, marker="s", linewidth=1.8, markersize=4.5, label="Standard RLM")
    # Hollow marker: Direct and Standard RLM land on the same value at 16k and
    # 131k, and a filled triangle hid the square underneath it.
    left.plot(x, length_rates["direct_controller"], color=GRAY_EDGE, marker="^", linewidth=1.5, markersize=4.5, linestyle="--", label="Direct", markerfacecolor="white", markeredgewidth=1.0)
    # \textit{N} rather than $N$: TeX math mode set the variable in Computer
    # Modern serif inside an otherwise sans panel.
    left.set_title(r"(a) Descriptive Oolong \textit{N}=120 by context length", pad=3)
    left.set_ylabel(r"Exact rate (\%)")
    left.set_xlabel("Context tokens (24 questions/bucket)", labelpad=1)
    left.set_xticks(x, length_labels)
    # The legend must not sit in the lower-left band: the standard-RLM series
    # falls to about 16% at the 65k bucket and crosses that region, so a
    # frameless lower-left legend collides with plotted data. The upper band is
    # empty because the highest plotted point is 79.2% at 16k.
    style_axis(left, upper=126)
    # Anchored into the reserved 100-126 band. At upper=118 the legend row sat
    # directly on the y=100 gridline and read as data at y=100.
    left.legend(loc="upper center", bbox_to_anchor=(0.5, 1.01), ncol=3, frameon=False,
                handlelength=1.5, columnspacing=0.8, handletextpad=0.4, borderaxespad=0.0)
    left.spines["left"].set_bounds(0, 100)

    seed20 = load_browse_rollout(SEED20_ANALYSIS, "active_runtime_listed_rate_usd")
    seed21 = load_browse_rollout(SEED21_ANALYSIS, "active_runtime_usd")
    route_colors = [GOLD, BLUE, GREEN, GRAY]
    route_edges = [GOLD_EDGE, BLUE_EDGE, GREEN_EDGE, GRAY_EDGE]

    for route_index, (color, edge) in enumerate(zip(route_colors, route_edges)):
        right.plot(
            [seed20["cost"][route_index], seed21["cost"][route_index]],
            [seed20["accuracy"][route_index], seed21["accuracy"][route_index]],
            color=edge,
            linewidth=0.9,
            alpha=0.65,
            zorder=1,
        )
        for rollout, marker, face in [
            (seed20, "o", color),
            (seed21, "D", "white"),
        ]:
            right.errorbar(
                rollout["cost"][route_index],
                rollout["accuracy"][route_index],
                yerr=rollout["error"][:, route_index : route_index + 1],
                fmt="none",
                ecolor=edge,
                elinewidth=0.9,
                capsize=2.5,
                capthick=0.9,
                zorder=2,
            )
            right.scatter(
                rollout["cost"][route_index],
                rollout["accuracy"][route_index],
                # Marker area exposes route call count within each rollout.
                s=20 + 0.08 * rollout["calls"][route_index],
                marker=marker,
                facecolors=face,
                edgecolors=edge,
                linewidths=1.0,
                zorder=3,
            )

    # Route labels attach to the prospective endpoint; marker shape identifies
    # the same-row post-hoc repeat. Color and short leader lines make attachment
    # unambiguous in the clustered adaptive-route band at final print size.
    placements = [
        (-4, 12, "center", "bottom"),  # RLM
        (17, -7, "left", "top"),       # Iterative
        (-16, 10, "right", "bottom"),  # Text
        (6, 9, "left", "bottom"),      # BM25
    ]
    for cost, accuracy, label, edge, (dx, dy, ha, va) in zip(
        seed20["cost"], seed20["accuracy"], BROWSE_LABELS, route_edges, placements
    ):
        right.annotate(
            label,
            (cost, accuracy),
            xytext=(dx, dy),
            textcoords="offset points",
            ha=ha,
            va=va,
            fontsize=9.0,
            color=edge,
            bbox=dict(facecolor="white", edgecolor="none", pad=0.6),
            arrowprops=dict(
                arrowstyle="-",
                color=edge,
                linewidth=0.7,
                shrinkA=1.5,
                shrinkB=4.0,
            ),
        )

    right.set_title("(b) Equal-cap BrowseComp+ rollouts", pad=3)
    right.set_ylabel(r"Semantic acc. (\%)")
    right.set_xlabel(r"Active-runtime cost (USD, log scale)", labelpad=1)
    right.set_xscale("log")
    right.set_xlim(0.18, 28.0)
    right.set_xticks([0.3, 1.0, 3.0, 10.0], [r"\$0.3", r"\$1", r"\$3", r"\$10"])
    right.set_ylim(25, 118)
    right.set_yticks(np.arange(30, 91, 20), [str(v) for v in range(30, 91, 20)])
    right.grid(axis="both", color="#D7D7D7", linewidth=0.7)
    right.set_axisbelow(True)
    right.spines[["top", "right"]].set_visible(False)
    right.spines["left"].set_bounds(30, 100)
    right.legend(
        handles=[
            Line2D([0], [0], marker="o", color="#202020", markerfacecolor="#202020",
                   linewidth=0, markersize=5.5, label="Seed 20: prospective"),
            Line2D([0], [0], marker="D", color="#202020", markerfacecolor="white",
                   linewidth=0, markersize=5.0, label="Seed 21: post-hoc"),
        ],
        loc="upper center",
        bbox_to_anchor=(0.5, 1.01),
        ncol=2,
        frameon=False,
        handletextpad=0.25,
        columnspacing=0.7,
        borderaxespad=0.0,
        fontsize=8.4,
    )

    # Preserve the declared 7.2-inch page width. Tight-bbox export expands the
    # canvas around labels and would shrink nominal font sizes when LaTeX fits
    # the graphic to text width.
    fig.savefig(OUT.with_suffix(".pdf"))
    plt.close(fig)
    subprocess.run(
        [
            "pdftoppm",
            "-png",
            "-r",
            "300",
            "-singlefile",
            str(OUT.with_suffix(".pdf")),
            str(OUT),
        ],
        check=True,
    )


if __name__ == "__main__":
    main()
