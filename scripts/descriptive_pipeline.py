#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import argparse
import json
from dataclasses import dataclass

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from scipy.stats import skew, kurtosis, shapiro, sem, t

from plot_style import apply_bae_style, get_publication_palette

QC_EXCLUDE = "孙校聪,康少勇,张钰鹏,杨可,洪婷婷,陈韬,高梓楠,赵国宏"
S_COLS = ["S1", "S2", "S3", "S4", "S5"]
B_COLS = ["B1", "B2", "B3", "Bmean"]
IPQ_COLS = ["IPQ1", "IPQ2", "IPQ3", "IPQ4", "IPQ5", "IPQ6", "IPQ_mean"]
LIKERT_LIMS = (1, 10)
LIKERT_TICKS = list(range(1, 11))


def _exclude_subjects(df: pd.DataFrame, text: str) -> pd.DataFrame:
    if not text or "SubjectID" not in df.columns:
        return df
    names = [x.strip() for x in str(text).split(",") if x.strip()]
    if not names:
        return df
    sid = df["SubjectID"].astype(str).str.strip()
    return df.loc[~sid.isin(set(names))].copy()


def _ci95(z: pd.Series) -> tuple[float, float]:
    zz = pd.to_numeric(z, errors="coerce").dropna()
    n = int(len(zz))
    if n < 2:
        return np.nan, np.nan
    m = float(zz.mean())
    se = float(sem(zz, nan_policy="omit"))
    h = float(t.ppf(0.975, df=n - 1) * se)
    return m - h, m + h


def _norm_p(z: pd.Series) -> float:
    zz = pd.to_numeric(z, errors="coerce").dropna()
    if len(zz) < 3 or len(zz) > 5000:
        return np.nan
    try:
        return float(shapiro(zz).pvalue)
    except Exception:
        return np.nan


def _desc_stats(z: pd.Series, subject_ids: pd.Series | None = None) -> dict[str, float]:
    zz = pd.to_numeric(z, errors="coerce")
    valid = zz.notna()
    zz = zz[valid]
    n_obs = int(len(zz))
    n_subjects = int(subject_ids[valid].astype(str).str.strip().nunique()) if subject_ids is not None else n_obs
    ci_low, ci_high = _ci95(zz)
    return {
        "n": n_subjects,
        "n_obs": n_obs,
        "mean": float(zz.mean()) if n_obs else np.nan,
        "sd": float(zz.std(ddof=1)) if n_obs > 1 else np.nan,
        "median": float(zz.median()) if n_obs else np.nan,
        "min": float(zz.min()) if n_obs else np.nan,
        "max": float(zz.max()) if n_obs else np.nan,
        "skewness": float(skew(zz, bias=False)) if n_obs > 2 else np.nan,
        "kurtosis": float(kurtosis(zz, fisher=True, bias=False)) if n_obs > 3 else np.nan,
        "ci95_low": ci_low,
        "ci95_high": ci_high,
        "shapiro_p": _norm_p(zz),
    }


def _desc_table(df: pd.DataFrame, cols: list[str], group_cols: list[str] | None = None) -> pd.DataFrame:
    rows = []
    use_cols = [c for c in cols if c in df.columns]
    if not use_cols:
        return pd.DataFrame()

    group_cols = group_cols or []
    if group_cols:
        grouped = df.groupby(group_cols, dropna=False)
        iter_items = list(grouped)
    else:
        iter_items = [((), df.copy())]

    for key, sub in iter_items:
        if not isinstance(key, tuple):
            key = (key,)
        key_map = dict(zip(group_cols, key)) if group_cols else {"Group": "ALL"}
        for c in use_cols:
            rows.append({**key_map, "DV": c, **_desc_stats(sub[c], sub["SubjectID"] if "SubjectID" in sub.columns else None)})
    return pd.DataFrame(rows)


def _subject_level_ipq(df: pd.DataFrame) -> pd.DataFrame:
    if "SubjectID" not in df.columns:
        return df.copy()
    return df.groupby("SubjectID", as_index=False).first()


def _fmt_num(v: float | None, nd: int = 2) -> str:
    if v is None or pd.isna(v):
        return "NA"
    return f"{float(v):.{nd}f}"


def _format_group_value(v) -> str:
    if pd.isna(v):
        return "NA"
    try:
        fv = float(v)
        if fv.is_integer():
            return str(int(fv))
    except Exception:
        pass
    return str(v)


def _annotation_lines(sub: pd.DataFrame, dv: str, group_col: str | None = None) -> list[str]:
    if group_col and group_col in sub.columns:
        lines = []
        for g, sg in sub.groupby(group_col, dropna=False):
            st = _desc_stats(sg[dv], sg["SubjectID"] if "SubjectID" in sg.columns else None)
            lines.append(f"{_format_group_value(g)}: n={st['n']}, M={_fmt_num(st['mean'])}±{_fmt_num(st['sd'])}")
        return lines
    st = _desc_stats(sub[dv], sub["SubjectID"] if "SubjectID" in sub.columns else None)
    return [f"n={st['n']}, M={_fmt_num(st['mean'])}±{_fmt_num(st['sd'])}"]


@dataclass
class _LabelSpec:
    x: float
    y: float
    text: str
    wwr: str
    group: str
    stats: dict[str, float]


def _publication_title(dv: str, xcol: str | None, hue: str | None, kind_label: str) -> str:
    if xcol and hue and xcol != hue:
        return f"{dv} by {xcol} and {hue} ({kind_label})"
    if xcol:
        return f"{dv} across {xcol} ({kind_label})"
    if hue:
        return f"{dv} by {hue} ({kind_label})"
    return f"{dv} distribution ({kind_label})"


def _set_likert_axis(ax, dv: str) -> None:
    dv_upper = dv.upper()
    if dv_upper.startswith("S") or dv_upper.startswith("B") or dv_upper.startswith("IPQ"):
        ax.set_ylim(*LIKERT_LIMS)
        ax.set_yticks(LIKERT_TICKS)


def _finalize_axis(ax, dv: str, xcol: str | None, title: str) -> None:
    ax.set_title(title, pad=8)
    ax.set_xlabel(xcol if xcol else "")
    ax.set_ylabel(dv)
    ax.tick_params(axis="x", rotation=0)
    ax.grid(axis="y", linestyle="-", linewidth=0.55, alpha=0.22)
    ax.grid(axis="x", visible=False)
    _set_likert_axis(ax, dv)


def _summary_box(ax, title: str, lines: list[str]) -> None:
    ax.axis("off")
    ax.set_facecolor("#F7FAFD")
    ax.text(0.04, 0.97, title, va="top", ha="left", fontsize=10.0, fontweight="bold", color="#40534C")
    ax.text(
        0.04,
        0.90,
        "\n".join(lines),
        transform=ax.transAxes,
        va="top",
        ha="left",
        fontsize=8.2,
        color="#4E5E6A",
        linespacing=1.35,
        bbox=dict(boxstyle="round,pad=0.38", fc="white", ec="#D7E0E8", lw=0.75, alpha=0.96),
    )


def _cluster_annotation_map(sub: pd.DataFrame, dv: str, xcol: str | None, hue: str | None) -> dict[str, list[str]]:
    if not xcol or xcol not in sub.columns:
        return {"ALL": _annotation_lines(sub, dv, group_col=(hue if hue in sub.columns else None))}

    lines_map: dict[str, list[str]] = {}
    x_order = _get_order(sub[xcol])
    use_hue = hue if hue and hue in sub.columns and hue != xcol else None
    for xv in x_order:
        sx = sub[sub[xcol] == xv]
        if sx.empty:
            continue
        if use_hue:
            cluster_lines = []
            for hv, sh in sx.groupby(use_hue, dropna=False):
                st = _desc_stats(sh[dv], sh["SubjectID"] if "SubjectID" in sh.columns else None)
                cluster_lines.append(f"{_format_group_value(hv)}: M={_fmt_num(st['mean'])}, SD={_fmt_num(st['sd'])}")
        else:
            st = _desc_stats(sx[dv], sx["SubjectID"] if "SubjectID" in sx.columns else None)
            cluster_lines = [f"M={_fmt_num(st['mean'])}, SD={_fmt_num(st['sd'])}"]
        lines_map[str(xv)] = cluster_lines
    return lines_map


def _sample_size_legend_lines(sub: pd.DataFrame, hue: str | None = None) -> list[str]:
    if hue and hue in sub.columns:
        lines = []
        for hv, sh in sub.groupby(hue, dropna=False):
            n = sh["SubjectID"].astype(str).str.strip().nunique() if "SubjectID" in sh.columns else len(sh)
            lines.append(f"{_format_group_value(hv)}: n={n}")
        return lines
    n = sub["SubjectID"].astype(str).str.strip().nunique() if "SubjectID" in sub.columns else len(sub)
    return [f"Total participants: n={n}"]


def _annotate_cluster_stats(ax, sub: pd.DataFrame, dv: str, xcol: str | None, hue: str | None = None) -> None:
    return


def _compute_group_layout(sub: pd.DataFrame, xcol: str | None, hue: str | None) -> tuple[list[_LabelSpec], str | None]:
    work = sub.copy()
    if xcol and xcol in work.columns:
        work[xcol] = work[xcol].map(_normalize_category_value)
    if hue and hue in work.columns:
        work[hue] = work[hue].map(_normalize_category_value)

    if not xcol or xcol not in work.columns:
        return [], None

    x_order = _get_order(work[xcol])
    hue_arg = hue if hue and hue in work.columns and hue != xcol else None
    hue_order = _get_order(work[hue_arg]) if hue_arg else []
    width = 0.78
    dodge_span = min(width, 0.72)

    rows = []
    for xi, xv in enumerate(x_order):
        sx = work[work[xcol] == xv]
        if sx.empty:
            continue
        if hue_arg:
            n_h = max(1, len(hue_order))
            for hi, hv in enumerate(hue_order):
                sh = sx[sx[hue_arg] == hv]
                if sh.empty:
                    continue
                offset = (-dodge_span / 2.0) + ((hi + 0.5) * dodge_span / n_h)
                rows.append((xi + offset, xv, hv, sh))
        else:
            rows.append((float(xi), xv, xv, sx))
    return rows, hue_arg


def _build_label_specs(sub: pd.DataFrame, dv: str, xcol: str | None, hue: str | None, mode: str) -> list[_LabelSpec]:
    if not xcol or xcol not in sub.columns:
        st = _desc_stats(sub[dv], sub["SubjectID"] if "SubjectID" in sub.columns else None)
        if mode == "ci":
            text = f"M={_fmt_num(st['mean'])} [{_fmt_num(st['ci95_low'])}, {_fmt_num(st['ci95_high'])}]"
        else:
            text = f"M={_fmt_num(st['mean'])}, SD={_fmt_num(st['sd'])}"
        return [_LabelSpec(x=0.05, y=float(st["median"]), text=text, wwr="NA", group="ALL", stats=st)]

    layout_rows, hue_arg = _compute_group_layout(sub, xcol, hue)
    specs: list[_LabelSpec] = []
    for x, xv, gv, sg in layout_rows:
        st = _desc_stats(sg[dv], sg["SubjectID"] if "SubjectID" in sg.columns else None)
        if mode == "ci":
            text = f"M={_fmt_num(st['mean'])} [{_fmt_num(st['ci95_low'])}, {_fmt_num(st['ci95_high'])}]"
        else:
            text = f"M={_fmt_num(st['mean'])}, SD={_fmt_num(st['sd'])}"
        wwr_v = str(xv) if xcol == "WWR" else (str(sg["WWR"].iloc[0]) if "WWR" in sg.columns and len(sg["WWR"].dropna()) else "NA")
        group_v = str(gv) if hue_arg else str(xv)
        specs.append(_LabelSpec(x=float(x) + 0.05, y=float(st["median"]), text=text, wwr=wwr_v, group=group_v, stats=st))
    return specs


def _apply_label_collision_offsets(ax, specs: list[_LabelSpec], min_gap_px: float = 16.0, shift_px: float = 14.0) -> list[tuple[_LabelSpec, float]]:
    if not specs:
        return []
    with_offsets: list[tuple[_LabelSpec, float]] = []
    sorted_specs = sorted(specs, key=lambda s: s.y)
    prev_display_y = None
    current_shift = 0.0
    for spec in sorted_specs:
        disp_y = ax.transData.transform((spec.x, spec.y))[1]
        if prev_display_y is not None and (disp_y + current_shift - prev_display_y) < min_gap_px:
            current_shift += shift_px
        shifted = disp_y + current_shift
        prev_display_y = shifted
        with_offsets.append((spec, current_shift))
    return with_offsets


def _annotate_compact_labels(ax, specs: list[_LabelSpec]) -> None:
    for spec, shift_px in _apply_label_collision_offsets(ax, specs):
        ax.annotate(
            spec.text,
            xy=(spec.x, spec.y),
            xycoords="data",
            xytext=(5, 7 + shift_px),
            textcoords="offset points",
            ha="left",
            va="bottom",
            fontsize=7.3,
            color="#3E4D5A",
            bbox=dict(boxstyle="round,pad=0.20", fc="white", ec="#D7E0E8", lw=0.6, alpha=0.78),
            zorder=6,
            clip_on=False,
        )


def _export_plot_stats_csv(path: Path, specs: list[_LabelSpec]) -> Path:
    rows = []
    for spec in specs:
        rows.append(
            {
                "WWR": spec.wwr,
                "group": spec.group,
                "n": spec.stats["n"],
                "mean": spec.stats["mean"],
                "sd": spec.stats["sd"],
                "median": spec.stats["median"],
                "ci95_low": spec.stats["ci95_low"],
                "ci95_high": spec.stats["ci95_high"],
            }
        )
    out_path = path.with_suffix("")
    out_path = out_path.with_name(f"{out_path.name}_plot_stats.csv")
    pd.DataFrame(rows).to_csv(out_path, index=False, encoding="utf-8-sig")
    return out_path


def _normalize_category_value(v):
    if pd.isna(v):
        return np.nan
    try:
        fv = float(v)
        if fv.is_integer():
            return str(int(fv))
        return str(fv)
    except Exception:
        return str(v)


def _get_order(series: pd.Series) -> list:
    vals = [_normalize_category_value(v) for v in series.dropna().unique().tolist()]
    vals = [v for v in vals if pd.notna(v)]
    try:
        return sorted(vals, key=lambda x: float(x))
    except Exception:
        return sorted(vals, key=lambda x: str(x))


def _get_grouped_palette(sub: pd.DataFrame, hue: str | None) -> dict | None:
    if not hue or hue not in sub.columns:
        return None
    levels = _get_order(sub[hue])
    colors = get_publication_palette(len(levels))
    return {str(level): colors[i] for i, level in enumerate(levels)}


def _plot_box(ax, sub: pd.DataFrame, dv: str, xcol: str | None, hue: str | None, palette) -> None:
    if xcol and xcol in sub.columns:
        hue_arg = hue if hue in sub.columns and hue != xcol else xcol
        x_order = _get_order(sub[xcol])
        hue_order = _get_order(sub[hue_arg]) if hue_arg and hue_arg in sub.columns else None
        sns.boxplot(
            data=sub,
            x=xcol,
            y=dv,
            hue=hue_arg,
            order=x_order,
            hue_order=hue_order,
            palette=palette,
            width=0.42,
            fliersize=0,
            linewidth=1.05,
            dodge=(hue_arg != xcol),
            saturation=0.88,
            boxprops=dict(alpha=0.42),
            whiskerprops=dict(alpha=0.9),
            capprops=dict(alpha=0.9),
            medianprops=dict(color="#2F3B46", linewidth=1.25),
            ax=ax,
        )
        sns.pointplot(
            data=sub,
            x=xcol,
            y=dv,
            hue=hue_arg,
            order=x_order,
            hue_order=hue_order,
            palette=palette,
            dodge=0.52 if hue_arg != xcol else False,
            join=False,
            markers="D",
            ax=ax,
        )
    else:
        sns.boxplot(
            data=sub,
            y=dv,
            color="#D7E7F5",
            width=0.28,
            fliersize=0,
            linewidth=1.05,
            boxprops=dict(alpha=0.5),
            medianprops=dict(color="#2F3B46", linewidth=1.25),
            ax=ax,
        )
        mean = pd.to_numeric(sub[dv], errors="coerce").mean()
        ax.scatter([0], [mean], marker="D", s=28, color="#2F3B46", zorder=4)


def _plot_jitter(ax, sub: pd.DataFrame, dv: str, xcol: str | None, hue: str | None, palette) -> None:
    if xcol and xcol in sub.columns:
        hue_arg = hue if hue in sub.columns and hue != xcol else xcol
        x_order = _get_order(sub[xcol])
        hue_order = _get_order(sub[hue_arg]) if hue_arg and hue_arg in sub.columns else None
        sns.stripplot(
            data=sub,
            x=xcol,
            y=dv,
            hue=hue_arg,
            order=x_order,
            hue_order=hue_order,
            palette=palette,
            dodge=(hue_arg != xcol),
            jitter=0.11,
            size=2.4,
            alpha=0.35,
            linewidth=0,
            ax=ax,
        )
        sns.pointplot(
            data=sub,
            x=xcol,
            y=dv,
            hue=hue_arg,
            order=x_order,
            hue_order=hue_order,
            palette=palette,
            dodge=0.52 if hue_arg != xcol else False,
            join=False,
            markers="D",
            ax=ax,
        )
    else:
        sns.stripplot(data=sub, y=dv, color="#6FA8DC", jitter=0.08, size=2.4, alpha=0.32, linewidth=0, ax=ax)
        mean = pd.to_numeric(sub[dv], errors="coerce").mean()
        ax.scatter([0], [mean], marker="D", s=28, color="#2F3B46", zorder=4)


def _plot_box_mean_ci(ax, sub: pd.DataFrame, dv: str, xcol: str | None, hue: str | None, palette) -> None:
    if xcol and xcol in sub.columns:
        hue_arg = hue if hue in sub.columns and hue != xcol else xcol
        x_order = _get_order(sub[xcol])
        hue_order = _get_order(sub[hue_arg]) if hue_arg and hue_arg in sub.columns else None
        sns.boxplot(
            data=sub,
            x=xcol,
            y=dv,
            hue=hue_arg,
            order=x_order,
            hue_order=hue_order,
            palette=palette,
            width=0.40,
            fliersize=0,
            linewidth=1.0,
            dodge=(hue_arg != xcol),
            boxprops=dict(alpha=0.34),
            whiskerprops=dict(alpha=0.88),
            medianprops=dict(color="#2F3B46", linewidth=1.2),
            ax=ax,
        )
        sns.pointplot(
            data=sub,
            x=xcol,
            y=dv,
            hue=hue_arg,
            order=x_order,
            hue_order=hue_order,
            palette=palette,
            dodge=0.36 if hue_arg != xcol else False,
            ci=95,
            markers="D",
            ax=ax,
        )
    else:
        sns.boxplot(
            data=sub,
            y=dv,
            color="#C9D7E8",
            width=0.34,
            fliersize=0,
            linewidth=1.0,
            boxprops=dict(alpha=0.32),
            ax=ax,
        )
        mean = pd.to_numeric(sub[dv], errors="coerce").mean()
        low, high = _ci95(sub[dv])
        ax.errorbar([0], [mean], yerr=[[mean - low], [high - mean]], fmt="D", color="#2F3B46", capsize=4, lw=1.0)


def _plot_violin(ax, sub: pd.DataFrame, dv: str, xcol: str | None, hue: str | None, palette) -> None:
    if xcol and xcol in sub.columns:
        hue_arg = hue if hue in sub.columns and hue != xcol else xcol
        x_order = _get_order(sub[xcol])
        hue_order = _get_order(sub[hue_arg]) if hue_arg and hue_arg in sub.columns else None
        sns.violinplot(
            data=sub,
            x=xcol,
            y=dv,
            hue=hue_arg,
            order=x_order,
            hue_order=hue_order,
            palette=palette,
            inner=None,
            cut=0,
            linewidth=0.85,
            saturation=0.58,
            dodge=(hue_arg != xcol),
            ax=ax,
        )
        sns.boxplot(
            data=sub,
            x=xcol,
            y=dv,
            hue=hue_arg,
            order=x_order,
            hue_order=hue_order,
            palette=palette,
            width=0.18,
            fliersize=0,
            linewidth=0.95,
            dodge=(hue_arg != xcol),
            boxprops=dict(alpha=0.5),
            whiskerprops=dict(alpha=0.9),
            medianprops=dict(color="#2F3B46", linewidth=1.15),
            ax=ax,
        )
        sns.pointplot(
            data=sub,
            x=xcol,
            y=dv,
            hue=hue_arg,
            order=x_order,
            hue_order=hue_order,
            palette=palette,
            dodge=0.36 if hue_arg != xcol else False,
            ci=95,
            markers="D",
            ax=ax,
        )
    else:
        sns.violinplot(data=sub, y=dv, color="#D5E1EF", inner=None, cut=0, linewidth=0.9, saturation=0.72, ax=ax)
        sns.boxplot(data=sub, y=dv, color="#AFC3DD", width=0.16, fliersize=0, linewidth=0.95, boxprops=dict(alpha=0.55), ax=ax)
        mean = pd.to_numeric(sub[dv], errors="coerce").mean()
        low, high = _ci95(sub[dv])
        ax.errorbar([0], [mean], yerr=[[mean - low], [high - mean]], fmt="D", color="#2F3B46", capsize=4, lw=1.0)


def _dedupe_legend(ax) -> None:
    handles, labels = ax.get_legend_handles_labels()
    if not handles:
        return
    seen = set()
    new_handles = []
    new_labels = []
    for h, l in zip(handles, labels):
        if l in seen or l == "":
            continue
        seen.add(l)
        new_handles.append(h)
        new_labels.append(l)
    if new_handles:
        ax.legend(new_handles, new_labels, loc="upper left", bbox_to_anchor=(0.0, 1.02), ncol=min(3, len(new_labels)))


def _plot_distribution_panels(df: pd.DataFrame, cols: list[str], out_dir: Path, prefix: str, hue: str | None = None, xcol: str | None = None) -> list[str]:
    made = []
    use_cols = [c for c in cols if c in df.columns]
    if not use_cols:
        return made
    out_dir.mkdir(parents=True, exist_ok=True)

    for dv in use_cols:
        sub = df.dropna(subset=[dv]).copy()
        if sub.empty:
            continue

        if xcol and xcol in sub.columns:
            sub[xcol] = sub[xcol].map(_normalize_category_value)
        if hue and hue in sub.columns:
            sub[hue] = sub[hue].map(_normalize_category_value)

        palette = _get_grouped_palette(sub, hue if hue in sub.columns and hue != xcol else xcol if xcol in sub.columns else None)
        plot_specs = [
            ("box", _plot_box, "box"),
            ("jitter", _plot_jitter, "jitter"),
            ("box_mean_ci", _plot_box_mean_ci, "box+mean±95% CI"),
            ("violin", _plot_violin, "violin"),
        ]

        for kind_key, plot_fn, kind_label in plot_specs:
            fig, ax = plt.subplots(figsize=(8.4, 4.8))
            plot_fn(ax, sub, dv, xcol, hue, palette)
            _finalize_axis(ax, dv, xcol, _publication_title(dv, xcol, hue if hue != xcol else None, kind_label))
            _dedupe_legend(ax)
            stats_mode = "ci" if kind_key in {"box_mean_ci", "violin"} else "sd"
            specs = _build_label_specs(sub, dv, xcol, hue if hue in sub.columns and hue != xcol else None, stats_mode)
            _annotate_compact_labels(ax, specs)
            fig.tight_layout()
            path = out_dir / f"{prefix}_{dv}_{kind_key}.png"
            fig.savefig(path, dpi=300, bbox_inches="tight")
            stats_path = _export_plot_stats_csv(path, specs)
            plt.close(fig)
            made.append(str(path))
            made.append(str(stats_path))
    return made


def main():
    ap = argparse.ArgumentParser(description="Descriptive-only pipeline: overall + experience")
    ap.add_argument("--long-csv", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, default=Path("results/descriptive"))
    ap.add_argument("--with-qc", action="store_true", help="Also export QC-excluded outputs")
    args = ap.parse_args()

    apply_bae_style()

    out = args.out_dir
    out.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(args.long_csv)

    branches = [("raw", "")]
    if args.with_qc:
        branches.append(("qc", QC_EXCLUDE))

    outputs: list[str] = []

    for branch, exclude in branches:
        base = out / branch
        base.mkdir(parents=True, exist_ok=True)
        x = _exclude_subjects(df, exclude)

        overall_dir = base / "overall"
        overall_dir.mkdir(parents=True, exist_ok=True)
        csv_dir_overall = overall_dir / "csv"
        png_dir_overall = overall_dir / "png"
        csv_dir_overall.mkdir(parents=True, exist_ok=True)
        png_dir_overall.mkdir(parents=True, exist_ok=True)
        fig_dir_overall = png_dir_overall

        s_overall = _desc_table(x, S_COLS)
        s_overall_wwr = _desc_table(x, S_COLS, ["WWR"]) if "WWR" in x.columns else pd.DataFrame()
        s_overall_cx = _desc_table(x, S_COLS, ["Complexity"]) if "Complexity" in x.columns else pd.DataFrame()

        b_src = x[x["Complexity"].astype(str).isin(["1", "1.0"])].copy() if "Complexity" in x.columns else x
        b_overall = _desc_table(b_src, B_COLS)
        b_overall_wwr = _desc_table(b_src, B_COLS, ["WWR"]) if "WWR" in b_src.columns else pd.DataFrame()

        ipq_subj = _subject_level_ipq(x)
        ipq_overall = _desc_table(ipq_subj, IPQ_COLS)

        s_overall.to_csv(csv_dir_overall / "s1_s5_descriptives.csv", index=False, encoding="utf-8-sig")
        s_overall_wwr.to_csv(csv_dir_overall / "s1_s5_descriptives_by_wwr.csv", index=False, encoding="utf-8-sig")
        s_overall_cx.to_csv(csv_dir_overall / "s1_s5_descriptives_by_complexity.csv", index=False, encoding="utf-8-sig")
        b_overall.to_csv(csv_dir_overall / "b1_b3_descriptives.csv", index=False, encoding="utf-8-sig")
        b_overall_wwr.to_csv(csv_dir_overall / "b1_b3_descriptives_by_wwr.csv", index=False, encoding="utf-8-sig")
        ipq_overall.to_csv(csv_dir_overall / "ipq_descriptives.csv", index=False, encoding="utf-8-sig")

        outputs += [
            str((csv_dir_overall / "s1_s5_descriptives.csv").relative_to(out)),
            str((csv_dir_overall / "s1_s5_descriptives_by_wwr.csv").relative_to(out)),
            str((csv_dir_overall / "s1_s5_descriptives_by_complexity.csv").relative_to(out)),
            str((csv_dir_overall / "b1_b3_descriptives.csv").relative_to(out)),
            str((csv_dir_overall / "b1_b3_descriptives_by_wwr.csv").relative_to(out)),
            str((csv_dir_overall / "ipq_descriptives.csv").relative_to(out)),
        ]

        for p in _plot_distribution_panels(x, S_COLS, fig_dir_overall, prefix="overall_s", xcol="WWR" if "WWR" in x.columns else None):
            outputs.append(str(Path(p).relative_to(out)))
        for p in _plot_distribution_panels(b_src, B_COLS, fig_dir_overall, prefix="overall_b", xcol="WWR" if "WWR" in b_src.columns else None):
            outputs.append(str(Path(p).relative_to(out)))

        if "ExperienceGroup" in x.columns:
            exp_dir = base / "experience"
            exp_dir.mkdir(parents=True, exist_ok=True)
            csv_dir_exp = exp_dir / "csv"
            png_dir_exp = exp_dir / "png"
            csv_dir_exp.mkdir(parents=True, exist_ok=True)
            png_dir_exp.mkdir(parents=True, exist_ok=True)
            fig_dir_exp = png_dir_exp

            s_exp = _desc_table(x, S_COLS, ["ExperienceGroup"])
            s_exp_wwr = _desc_table(x, S_COLS, ["ExperienceGroup", "WWR"]) if "WWR" in x.columns else pd.DataFrame()
            s_exp_cx = _desc_table(x, S_COLS, ["ExperienceGroup", "Complexity"]) if "Complexity" in x.columns else pd.DataFrame()

            b_exp = _desc_table(b_src, B_COLS, ["ExperienceGroup"])
            b_exp_wwr = _desc_table(b_src, B_COLS, ["ExperienceGroup", "WWR"]) if "WWR" in b_src.columns else pd.DataFrame()

            ipq_exp = _desc_table(ipq_subj, IPQ_COLS, ["ExperienceGroup"])

            s_exp.to_csv(csv_dir_exp / "s1_s5_descriptives_by_experience.csv", index=False, encoding="utf-8-sig")
            s_exp_wwr.to_csv(csv_dir_exp / "s1_s5_descriptives_by_experience_wwr.csv", index=False, encoding="utf-8-sig")
            s_exp_cx.to_csv(csv_dir_exp / "s1_s5_descriptives_by_experience_complexity.csv", index=False, encoding="utf-8-sig")
            b_exp.to_csv(csv_dir_exp / "b1_b3_descriptives_by_experience.csv", index=False, encoding="utf-8-sig")
            b_exp_wwr.to_csv(csv_dir_exp / "b1_b3_descriptives_by_experience_wwr.csv", index=False, encoding="utf-8-sig")
            ipq_exp.to_csv(csv_dir_exp / "ipq_descriptives_by_experience.csv", index=False, encoding="utf-8-sig")

            outputs += [
                str((csv_dir_exp / "s1_s5_descriptives_by_experience.csv").relative_to(out)),
                str((csv_dir_exp / "s1_s5_descriptives_by_experience_wwr.csv").relative_to(out)),
                str((csv_dir_exp / "s1_s5_descriptives_by_experience_complexity.csv").relative_to(out)),
                str((csv_dir_exp / "b1_b3_descriptives_by_experience.csv").relative_to(out)),
                str((csv_dir_exp / "b1_b3_descriptives_by_experience_wwr.csv").relative_to(out)),
                str((csv_dir_exp / "ipq_descriptives_by_experience.csv").relative_to(out)),
            ]

            for p in _plot_distribution_panels(x, S_COLS, fig_dir_exp, prefix="experience_s", hue="ExperienceGroup", xcol="WWR" if "WWR" in x.columns else "ExperienceGroup"):
                outputs.append(str(Path(p).relative_to(out)))
            for p in _plot_distribution_panels(b_src, B_COLS, fig_dir_exp, prefix="experience_b", hue="ExperienceGroup", xcol="WWR" if "WWR" in b_src.columns else "ExperienceGroup"):
                outputs.append(str(Path(p).relative_to(out)))

    payload = {
        "task": "descriptive pipeline",
        "scope": ["overall", "experience"],
        "branches": [b for b, _ in branches],
        "outputs": outputs,
        "stats": ["n", "mean", "sd", "median", "min", "max", "skewness", "kurtosis", "ci95", "shapiro_p"],
        "stratification": ["WWR", "Complexity", "ExperienceGroup"],
        "figure_style": "in-plot compact labels, no side panel",
    }
    (out / "descriptive_summary.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False))


if __name__ == "__main__":
    main()
