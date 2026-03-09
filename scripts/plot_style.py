#!/usr/bin/env python3
from __future__ import annotations

"""Unified plotting style for publication-ready figures (BAE-oriented).

Goals:
- clean white background
- readable sans-serif typography
- colorblind-friendly palette
- consistent line widths / dpi
"""

import matplotlib as mpl
import seaborn as sns


def apply_bae_style() -> None:
    sns.set_theme(style="whitegrid", context="paper")
    # Fresh B&E / Origin-like palette: soft teal, sage, sand, slate
    sns.set_palette(["#6FAF9F", "#8EC5B6", "#C8B98B", "#8FA3B8", "#A8C7CF", "#B7B39A"])

    mpl.rcParams.update({
        # Font
        "font.family": "sans-serif",
        "font.sans-serif": ["Arial", "DejaVu Sans", "Liberation Sans", "Noto Sans"],
        "font.size": 10,
        "axes.titlesize": 11,
        "axes.labelsize": 10,
        "xtick.labelsize": 9,
        "ytick.labelsize": 9,
        "legend.fontsize": 9,
        "figure.titlesize": 11,

        # Figure quality
        "figure.dpi": 220,
        "savefig.dpi": 300,
        "savefig.bbox": "tight",

        # Lines and axes
        "axes.linewidth": 0.8,
        "grid.linewidth": 0.6,
        "grid.alpha": 0.28,
        "grid.color": "#D7DDD8",
        "lines.linewidth": 1.8,
        "lines.markersize": 5.5,
        "axes.facecolor": "#FCFDFC",
        "figure.facecolor": "white",
        "axes.edgecolor": "#BFC8C2",

        # Minimal frame
        "axes.spines.top": False,
        "axes.spines.right": False,
    })
