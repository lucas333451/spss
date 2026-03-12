#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import argparse
import json

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
LIKERT_LIMS = (1, 7)
LIKERT_TICKS = list(range(1, 8))


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


def _desc_stats(z: pd.Series) -> dict[str, float]:
    zz = pd.to_numeric(z, errors="coerce").dropna()
    n = int(len(zz))
    ci_low, ci_high = _ci95(zz)
    return {
        "n": n,
        "mean": float(zz.mean()) if n else np.nan,
        "sd": float(zz.std(ddof=1)) if n > 1 else np.nan,
        "median": float(zz.median()) if n else np.nan,
        "min": float(zz.min()) if n else np.nan,
        "max": float(zz.max()) if n else np.nan,
        "skewness": float(skew(zz, bias=False)) if n > 2 else np.nan,
        "kurtosis": float(kurtosis(zz, fisher=True, bias=False)) if n > 3 else np.nan,
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
            rows.append({**key_map, "DV": c, **_desc_stats(sub[c])})
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
            st = _desc_stats(sg[dv])
            lines.append(f"{_format_group_value(g)}: n={st['n']}, M={_fmt_num(st['mean'])}±{_fmt_num(st['sd'])}")
        return lines
    st = _desc_stats(sub[dv])
    return [f"n={st['n']}, M={_fmt_num(st['mean'])}±{_fmt_num(st['sd'])}"]


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


def _annotate_key_stats(ax, sub: pd.DataFrame, dv: str, group_col: str | None = None) -> None:
    lines = _annotation_lines(sub, dv, group_col)
    text = "\n".join(lines)
    ax.text(
        0.99,
        0.98,
        text,
        transform=ax.transAxes,
        va="top",
        ha="right",
        fontsize=8.1,
        color="#3F4B57",
        bbox=dict(boxstyle="round,pad=0.28", fc="white", ec="#D7DDE4", lw=0.7, alpha=0.94),
    )


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


def _plot_box_jitter(ax, sub: pd.DataFrame, dv: str, xcol: str | None, hue: str | None, palette) -> None:
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
            width=0.56,
            fliersize=0,
            linewidth=1.0,
            dodge=(hue_arg != xcol),
            legend=False,
            ax=ax,
        )
        sns.stripplot(
            data=sub,
            x=xcol,
            y=dv,
            hue=hue_arg,
            order=x_order,
            hue_order=hue_order,
            palette=palette,
            dodge=(hue_arg != xcol),
            jitter=0.18,
            size=2.4,
            alpha=0.42,
            linewidth=0,
            legend=False,
            ax=ax,
        )
    else:
        sns.boxplot(data=sub, y=dv, color="#C9D7E8", width=0.34, fliersize=0, linewidth=1.0, ax=ax)
        sns.stripplot(data=sub, y=dv, color="#4C78A8", jitter=0.12, size=2.6, alpha=0.35, linewidth=0, ax=ax)


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
            width=0.52,
            fliersize=0,
            linewidth=1.0,
            dodge=(hue_arg != xcol),
            boxprops=dict(alpha=0.32),
            whiskerprops=dict(alpha=0.85),
            medianprops=dict(color="#2F3B46", linewidth=1.2),
            legend=False,
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
            errorbar=("ci", 95),
            linestyle="none",
            markers="D",
            markersize=6.2,
            err_kws={"linewidth": 1.0, "alpha": 0.95},
            legend=False,
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
            linewidth=0.9,
            saturation=0.72,
            dodge=(hue_arg != xcol),
            legend=False,
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
            legend=False,
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
            errorbar=("ci", 95),
            linestyle="none",
            markers="D",
            markersize=5.8,
            err_kws={"linewidth": 0.95, "alpha": 0.9},
            legend=False,
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
            ("box_jitter", _plot_box_jitter, "box+jitter"),
            ("box_mean_ci", _plot_box_mean_ci, "box+mean±95% CI"),
            ("violin", _plot_violin, "violin"),
        ]

        for kind_key, plot_fn, kind_label in plot_specs:
            fig, ax = plt.subplots(figsize=(6.2, 4.4))
            plot_fn(ax, sub, dv, xcol, hue, palette)
            _finalize_axis(ax, dv, xcol, _publication_title(dv, xcol, hue if hue != xcol else None, kind_label))
            _annotate_key_stats(ax, sub, dv, group_col=(hue if hue in sub.columns and hue != xcol else None))
            _dedupe_legend(ax)
            path = out_dir / f"{prefix}_{dv}_{kind_key}.png"
            fig.savefig(path, dpi=300)
            plt.close(fig)
            made.append(str(path))
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
        "figure_style": "publication palette; box+jitter and box+mean±CI recommended, violin retained as candidate; long summary panel removed; key n and M±SD kept in-figure",
    }
    (out / "descriptive_summary.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False))


if __name__ == "__main__":
    main()
