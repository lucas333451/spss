#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import argparse
import json

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from scipy.stats import f as f_dist
from statsmodels.stats.multitest import multipletests

from plot_style import apply_bae_style

S_DVS = ["S1", "S2", "S3", "S4", "S5"]
LINEAR_COEF = np.array([-1.0, 0.0, 1.0])
QUADRATIC_COEF = np.array([1.0, -2.0, 1.0])


def _sigstar(p: float | None) -> str:
    if p is None or pd.isna(p):
        return ""
    if p < 0.001:
        return "***"
    if p < 0.01:
        return "**"
    if p < 0.05:
        return "*"
    return ""


def _exclude_subjects(df: pd.DataFrame, text: str) -> pd.DataFrame:
    if not text:
        return df
    names = [x.strip() for x in str(text).split(",") if x.strip()]
    if not names or "SubjectID" not in df.columns:
        return df
    sid = df["SubjectID"].astype(str).str.strip()
    return df.loc[~sid.isin(set(names))].copy()


def _parse_levels(text: str) -> list[float]:
    vals = [float(x.strip()) for x in str(text).split(",") if x.strip()]
    if len(vals) != 3:
        raise SystemExit("--wwr-levels must contain exactly 3 comma-separated values, e.g. 15,45,75")
    return vals


def _level_label(level: float) -> str:
    return str(int(level)) if float(level).is_integer() else str(level)


def _subject_level_wide(df: pd.DataFrame, dv: str, levels: list[float], split_cols: list[str]) -> pd.DataFrame:
    sub = df.dropna(subset=["SubjectID", "WWR", dv]).copy()
    if sub.empty:
        return pd.DataFrame()

    sub["WWR"] = pd.to_numeric(sub["WWR"], errors="coerce")
    sub = sub[sub["WWR"].isin(levels)].copy()
    if sub.empty:
        return pd.DataFrame()

    grp_cols = ["SubjectID"] + split_cols + ["WWR"]
    agg = sub.groupby(grp_cols, as_index=False)[dv].mean()
    wide = agg.pivot_table(index=["SubjectID"] + split_cols, columns="WWR", values=dv, aggfunc="mean")

    for level in levels:
        if level not in wide.columns:
            wide[level] = np.nan

    wide = wide[levels].reset_index()
    rename_map = {level: f"WWR_{_level_label(level)}" for level in levels}
    return wide.rename(columns=rename_map)


def _contrast_glm_like(mat: np.ndarray, coef: np.ndarray) -> dict[str, float]:
    if mat.ndim != 2 or mat.shape[1] != len(coef):
        return {
            "n_subjects": 0,
            "mean_contrast": np.nan,
            "sd_contrast": np.nan,
            "se_contrast": np.nan,
            "ss": np.nan,
            "df1": 1.0,
            "df2": np.nan,
            "ms": np.nan,
            "mse": np.nan,
            "f": np.nan,
            "p": np.nan,
            "t": np.nan,
        }

    score = np.dot(mat, coef)
    score = score[np.isfinite(score)]
    n = int(len(score))
    if n < 2:
        mean_score = float(np.nanmean(score)) if n else np.nan
        return {
            "n_subjects": n,
            "mean_contrast": mean_score,
            "sd_contrast": np.nan,
            "se_contrast": np.nan,
            "ss": np.nan,
            "df1": 1.0,
            "df2": float(max(n - 1, 0)),
            "ms": np.nan,
            "mse": np.nan,
            "f": np.nan,
            "p": np.nan,
            "t": np.nan,
        }

    mean_score = float(np.mean(score))
    sd_score = float(np.std(score, ddof=1))
    se_score = float(sd_score / np.sqrt(n)) if n > 0 else np.nan
    df2 = float(n - 1)
    ss_effect = float(n * (mean_score ** 2))
    ss_error = float(np.sum((score - mean_score) ** 2))
    ms_effect = ss_effect
    mse = float(ss_error / df2) if df2 > 0 else np.nan
    if mse is not None and np.isfinite(mse) and mse > 0:
        f_value = float(ms_effect / mse)
        p_value = float(f_dist.sf(f_value, 1, df2))
    else:
        f_value = np.nan
        p_value = np.nan
    t_value = float(mean_score / se_score) if np.isfinite(se_score) and se_score > 0 else np.nan
    return {
        "n_subjects": n,
        "mean_contrast": mean_score,
        "sd_contrast": sd_score,
        "se_contrast": se_score,
        "ss": ss_effect,
        "df1": 1.0,
        "df2": df2,
        "ms": ms_effect,
        "mse": mse,
        "f": f_value,
        "p": p_value,
        "t": t_value,
    }


def _contrast_vector_column(levels: list[float], coef: np.ndarray) -> list[str]:
    return [f"WWR{_level_label(level)}:{float(c):g}" for level, c in zip(levels, coef)]


def _build_markdown(df: pd.DataFrame, out: Path, split_cols: list[str]) -> None:
    lines: list[str] = []
    lines.append("# Analysis-2 / Task5 — SPSS-style Within-Subjects Contrasts")
    lines.append("")
    lines.append("Approximates SPSS `Analyze → General Linear Model → Repeated Measures` with `WWR levels = 3` and `Contrasts = Polynomial`.")
    lines.append("")
    if split_cols:
        lines.append(f"Split columns: {', '.join(split_cols)}")
        lines.append("")

    if df.empty:
        lines.append("No valid results.")
        out.write_text("\n".join(lines), encoding="utf-8")
        return

    display_cols = split_cols + [
        "DV", "Source", "Contrast", "n_subjects", "Type III SS", "df", "Mean Square", "F", "Sig.", "SigAdj.", "SigStar"
    ]
    x = df[display_cols].copy()
    for c in ["Type III SS", "df", "Mean Square", "F", "Sig.", "SigAdj."]:
        x[c] = x[c].map(lambda v: "" if pd.isna(v) else f"{float(v):.4f}")
    lines.append(x.to_markdown(index=False))
    out.write_text("\n".join(lines), encoding="utf-8")


def _plot_trend_panels(means: pd.DataFrame, out_dir: Path, split_cols: list[str], levels: list[float]) -> list[str]:
    made: list[str] = []
    if means.empty:
        return made
    out_dir.mkdir(parents=True, exist_ok=True)

    for dv in sorted(means["DV"].dropna().unique()):
        x = means[means["DV"] == dv].copy()
        if x.empty:
            continue

        panel_col = split_cols[0] if split_cols else None
        hue_col = split_cols[1] if len(split_cols) >= 2 else None

        if panel_col and panel_col in x.columns:
            panel_values = list(pd.unique(x[panel_col]))
        else:
            panel_values = ["ALL"]
            x["__panel__"] = "ALL"
            panel_col = "__panel__"

        fig, axes = plt.subplots(1, len(panel_values), figsize=(max(5.0 * len(panel_values), 6.2), 4.2), sharey=True)
        if len(panel_values) == 1:
            axes = [axes]

        for ax, panel_val in zip(axes, panel_values):
            sub = x[x[panel_col] == panel_val].copy()
            if hue_col and hue_col in sub.columns:
                for hv, hg in sub.groupby(hue_col, dropna=False):
                    hg = hg.sort_values("WWR")
                    ax.plot(hg["WWR"], hg["mean"], marker="o", label=str(hv))
                    ax.fill_between(hg["WWR"], hg["mean"] - hg["se"], hg["mean"] + hg["se"], alpha=0.15)
            else:
                sub = sub.sort_values("WWR")
                ax.plot(sub["WWR"], sub["mean"], marker="o", color="#4E79A7")
                ax.fill_between(sub["WWR"], sub["mean"] - sub["se"], sub["mean"] + sub["se"], alpha=0.15, color="#4E79A7")
            ax.set_title(f"{panel_col} = {panel_val}" if panel_val != "ALL" else dv)
            ax.set_xlabel("WWR")
            ax.set_xticks(levels)
            ax.grid(alpha=0.2)

        axes[0].set_ylabel(dv)
        if hue_col and hue_col in x.columns:
            handles, labels = axes[0].get_legend_handles_labels()
            if handles:
                fig.legend(handles, labels, title=hue_col, loc="upper center", ncol=max(1, len(labels)))
                fig.tight_layout(rect=[0, 0, 1, 0.90])
            else:
                fig.tight_layout()
        else:
            fig.tight_layout()

        path = out_dir / f"task5_trend_profile_{dv}.png"
        fig.savefig(path, dpi=230)
        plt.close(fig)
        made.append(str(path))
    return made


def _plot_contrast_heatmaps(df: pd.DataFrame, out_dir: Path, split_cols: list[str], p_col: str, p_label: str) -> list[str]:
    made: list[str] = []
    if df.empty:
        return made
    out_dir.mkdir(parents=True, exist_ok=True)

    x = df[df["Source"] == "WWR"].copy()
    if x.empty:
        return made

    row_label_cols = split_cols[:] if split_cols else []
    if not row_label_cols:
        x["Panel"] = "ALL"
        x["RowLabel"] = "ALL"
        row_label_cols = ["Panel"]
    elif len(row_label_cols) == 1:
        x["Panel"] = x[row_label_cols[0]].astype(str)
        x["RowLabel"] = x[row_label_cols[0]].astype(str)
    else:
        x["Panel"] = x[row_label_cols[0]].astype(str)
        x["RowLabel"] = x[row_label_cols[1:]].astype(str).agg(" | ".join, axis=1)

    for contrast in ["Linear", "Quadratic"]:
        sub = x[x["Contrast"] == contrast].copy()
        if sub.empty:
            continue
        sub["Col"] = sub["DV"].astype(str)
        if "Repetition" in split_cols:
            sub["Col"] = sub["DV"].astype(str) + " | R" + sub["Repetition"].astype(str)

        mat = sub.pivot_table(index="RowLabel", columns="Col", values=p_col, aggfunc="first")
        if mat.empty:
            continue
        annot = mat.copy().astype(object)
        for r in annot.index:
            for c in annot.columns:
                p = annot.loc[r, c]
                if pd.isna(p):
                    annot.loc[r, c] = ""
                else:
                    pv = float(p)
                    if pv < 0.001:
                        ptxt = f"{pv:.2e}"
                    else:
                        ptxt = f"{pv:.3f}"
                    annot.loc[r, c] = f"p={ptxt}{_sigstar(pv)}"

        plt.figure(figsize=(max(8.5, 0.95 * len(mat.columns) + 2.5), max(3.0, 0.58 * len(mat.index) + 1.2)))
        sns.heatmap(
            -np.log10(mat.astype(float)),
            cmap="Blues",
            annot=annot,
            fmt="",
            annot_kws={"fontsize": 9},
            linewidths=0.6,
            linecolor="#efefef",
            cbar_kws={"label": f"-log10({p_label})"},
        )
        plt.title(f"Task5 {contrast} contrast significance map ({p_label})")
        plt.xlabel("DV")
        plt.ylabel("Split cell")
        plt.xticks(rotation=25, ha="right")
        plt.tight_layout()
        path = out_dir / f"task5_{contrast.lower()}_contrast_heatmap.png"
        plt.savefig(path, dpi=230)
        plt.close()
        made.append(str(path))
    return made


def main():
    ap = argparse.ArgumentParser(
        description="Analysis-2 Task5: SPSS-style repeated-measures polynomial contrasts across 3 WWR levels"
    )
    ap.add_argument("--long-csv", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, default=Path("results/research"))
    ap.add_argument("--wwr-levels", default="15,45,75", help="Exactly 3 comma-separated WWR levels in ascending order")
    ap.add_argument("--dvs", default=",".join(S_DVS), help="Comma-separated dependent variables, default S1,S2,S3,S4,S5")
    ap.add_argument("--split-by", default="", help="Optional comma-separated split columns, e.g. Repetition or ExperienceGroup")
    ap.add_argument("--exclude-subjects", default="", help="Comma-separated SubjectID list for QC exclusion")
    ap.add_argument("--p-adjust", default="none", help="Multiple-testing adjustment: holm|bonferroni|fdr_bh|none; default none to stay closer to SPSS output")
    args = ap.parse_args()

    apply_bae_style()

    out = args.out_dir
    out.mkdir(parents=True, exist_ok=True)
    fig_dir = out / "task5_spss_polynomial_figures"
    fig_dir.mkdir(parents=True, exist_ok=True)

    levels = _parse_levels(args.wwr_levels)
    dvs = [x.strip() for x in str(args.dvs).split(",") if x.strip()]
    split_cols = [x.strip() for x in str(args.split_by).split(",") if x.strip()]

    df = pd.read_csv(args.long_csv)
    df = _exclude_subjects(df, args.exclude_subjects)

    required = ["SubjectID", "WWR"] + split_cols
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise SystemExit(f"Missing required columns: {missing}")

    rows: list[dict] = []
    means_rows: list[dict] = []
    wide_exports: list[str] = []

    for dv in dvs:
        if dv not in df.columns:
            continue
        wide = _subject_level_wide(df, dv, levels, split_cols)
        wide_path = out / f"analysis2_task5_subject_means_{dv}.csv"
        wide.to_csv(wide_path, index=False, encoding="utf-8-sig")
        wide_exports.append(str(wide_path.relative_to(out)))

        level_cols = [f"WWR_{_level_label(level)}" for level in levels]
        grouped = wide.groupby(split_cols, dropna=False) if split_cols else [((), wide)]
        for key, g in grouped:
            split_values = {}
            if split_cols:
                if not isinstance(key, tuple):
                    key = (key,)
                split_values = dict(zip(split_cols, key))
            block = g.dropna(subset=level_cols, how="any").copy()
            mat = block[level_cols].to_numpy(dtype=float) if not block.empty else np.empty((0, 3))

            for i, level in enumerate(levels):
                vals = mat[:, i] if mat.size else np.array([], dtype=float)
                n = int(np.sum(np.isfinite(vals)))
                mean_val = float(np.nanmean(vals)) if n else np.nan
                sd_val = float(np.nanstd(vals, ddof=1)) if n >= 2 else np.nan
                se_val = float(sd_val / np.sqrt(n)) if n >= 2 and np.isfinite(sd_val) else np.nan
                mr = dict(split_values)
                mr.update({
                    "DV": dv,
                    "WWR": level,
                    "n_subjects": n,
                    "mean": mean_val,
                    "sd": sd_val,
                    "se": se_val,
                })
                means_rows.append(mr)

            for contrast_name, coef in [("Linear", LINEAR_COEF), ("Quadratic", QUADRATIC_COEF)]:
                stat = _contrast_glm_like(mat, coef)
                item = dict(split_values)
                item.update({
                    "DV": dv,
                    "Source": "WWR",
                    "Contrast": contrast_name,
                    "CoefficientVector": " | ".join(_contrast_vector_column(levels, coef)),
                    "n_subjects": stat["n_subjects"],
                    "Type III SS": stat["ss"],
                    "df": stat["df1"],
                    "Mean Square": stat["ms"],
                    "F": stat["f"],
                    "Sig.": stat["p"],
                    "Error SS": float(stat["mse"] * stat["df2"]) if np.isfinite(stat["mse"]) and np.isfinite(stat["df2"]) else np.nan,
                    "Error df": stat["df2"],
                    "Error MS": stat["mse"],
                    "t": stat["t"],
                    "mean_contrast": stat["mean_contrast"],
                    "sd_contrast": stat["sd_contrast"],
                    "se_contrast": stat["se_contrast"],
                    "status": "ok" if stat["n_subjects"] >= 2 else "insufficient_complete_subjects",
                })
                rows.append(item)

                err = dict(split_values)
                err.update({
                    "DV": dv,
                    "Source": "Error(WWR)",
                    "Contrast": contrast_name,
                    "CoefficientVector": " | ".join(_contrast_vector_column(levels, coef)),
                    "n_subjects": stat["n_subjects"],
                    "Type III SS": float(stat["mse"] * stat["df2"]) if np.isfinite(stat["mse"]) and np.isfinite(stat["df2"]) else np.nan,
                    "df": stat["df2"],
                    "Mean Square": stat["mse"],
                    "F": np.nan,
                    "Sig.": np.nan,
                    "Error SS": np.nan,
                    "Error df": np.nan,
                    "Error MS": np.nan,
                    "t": np.nan,
                    "mean_contrast": np.nan,
                    "sd_contrast": np.nan,
                    "se_contrast": np.nan,
                    "status": "ok" if stat["n_subjects"] >= 2 else "insufficient_complete_subjects",
                })
                rows.append(err)

    res = pd.DataFrame(rows)
    if not res.empty:
        res["SigAdj."] = res["Sig."]
        if args.p_adjust.lower() != "none":
            mask = (res["Source"] == "WWR") & res["Sig."].notna()
            res.loc[:, "SigAdj."] = np.nan
            res.loc[res["Source"] != "WWR", "SigAdj."] = np.nan
            if mask.any():
                _, padj, _, _ = multipletests(res.loc[mask, "Sig."].astype(float), method=args.p_adjust)
                res.loc[mask, "SigAdj."] = padj
        res["SigStar"] = res["SigAdj."].map(_sigstar)
        sort_cols = split_cols + ["DV", "Contrast", "Source"] if split_cols else ["DV", "Contrast", "Source"]
        res = res.sort_values(sort_cols).reset_index(drop=True)

    means_df = pd.DataFrame(means_rows)
    means_path = out / "analysis2_task5_wwr_profile_means.csv"
    csv_path = out / "analysis2_task5_spss_polynomial_contrasts.csv"
    md_path = out / "analysis2_task5_spss_polynomial_contrasts.md"
    summary_path = out / "analysis2_task5_spss_polynomial_summary.json"

    means_df.to_csv(means_path, index=False, encoding="utf-8-sig")
    res.to_csv(csv_path, index=False, encoding="utf-8-sig")
    _build_markdown(res, md_path, split_cols)

    figs: list[str] = []
    for p in _plot_trend_panels(means_df, fig_dir, split_cols, levels):
        figs.append(str(Path(p).relative_to(out)))
    p_col = "SigAdj." if args.p_adjust.lower() != "none" else "Sig."
    p_label = "adjusted p" if args.p_adjust.lower() != "none" else "raw p"
    for p in _plot_contrast_heatmaps(res, fig_dir, split_cols, p_col=p_col, p_label=p_label):
        figs.append(str(Path(p).relative_to(out)))

    payload = {
        "task": "analysis-2/task5 spss-style repeated-measures polynomial contrasts",
        "dvs": dvs,
        "wwr_levels": levels,
        "split_by": split_cols,
        "contrast_coefficients": {
            "Linear": LINEAR_COEF.tolist(),
            "Quadratic": QUADRATIC_COEF.tolist(),
        },
        "outputs": [
            str(csv_path.relative_to(out)),
            str(md_path.relative_to(out)),
            str(means_path.relative_to(out)),
            *wide_exports,
            *figs,
        ],
        "notes": [
            "Subject-level means are computed within each WWR level before contrast testing.",
            "For 3 WWR levels, Linear uses [-1, 0, 1] and Quadratic uses [1, -2, 1].",
            "Output table is organized to resemble SPSS Within-Subjects Contrasts (WWR / Error(WWR)).",
            "Default p-adjust is now 'none' to stay closer to SPSS repeated-measures output unless the user explicitly requests multiplicity correction.",
            "Each subject contributes one value per WWR level after within-subject averaging over any non-split repeated rows.",
            "PNG figures include WWR profile plots and contrast significance heatmaps for Linear/Quadratic contrasts.",
            "Interpret results from the observed data only; no expected-significance pattern is imposed or optimized for.",
        ],
    }
    summary_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False))


if __name__ == "__main__":
    main()
