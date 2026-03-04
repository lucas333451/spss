#!/usr/bin/env python3
from __future__ import annotations

"""Analysis-2 Task1: within-scene stage (Repetition) gap for S1–S5.

Goal (journal-friendly / auditable):
- For each SceneID (typically 6 scenes = 3 WWR × 2 conditions), compute within-subject gap between
  Stage2 (Repetition=2) and Stage1 (Repetition=1) for each DV (S1–S5).
- Stratify by people groups (default: PeopleGroup4 = Experience×SportFreq).
- Output per-scene group×DV table with p, sr, dz.
  - p: Wilcoxon signed-rank p-value (robust)
  - sr: signed-rank effect size r (approx from two-sided p; signed by delta direction)
  - dz: Cohen's dz for paired differences (mean(diff)/sd(diff))
- Save one PNG per scene (heatmap; rows=groups, cols=S1–S5).

Outputs (under out-dir, default results/research):
- analysis2_scene_stage_gap_long.csv
- analysis2_scene_stage_gap_wide_<SceneID>.csv (one per scene)
- analysis2_scene_stage_gap_figures/scene_<SceneID>.png (one per scene)

Assumptions:
- Two stages correspond to Repetition 1/2 (Round1/2).
- Uses SceneID from long table.
"""

from pathlib import Path
import argparse
import json

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from scipy.stats import ttest_rel, wilcoxon, norm

from analysis_groups import make_people_group4
from plot_style import apply_bae_style


DVS = ["S1", "S2", "S3", "S4", "S5"]


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


def _signed_rank_r_from_p(p: float, n: int, sign: float) -> float:
    """Approximate effect size r = z/sqrt(n) from two-sided p (normal approximation).

    This gives a magnitude consistent with common reporting; sign is provided separately.
    """
    if n <= 0 or pd.isna(p):
        return np.nan
    # avoid inf
    p = float(max(min(p, 1.0), 1e-300))
    z = float(norm.isf(p / 2.0))
    return float(np.sign(sign) * z / np.sqrt(n))


def _cohens_dz(diff: np.ndarray) -> float:
    diff = np.asarray(diff, dtype=float)
    diff = diff[np.isfinite(diff)]
    if len(diff) < 2:
        return np.nan
    sd = float(np.std(diff, ddof=1))
    if sd <= 0:
        return np.nan
    return float(np.mean(diff) / sd)


def _within_subject_pairs(df: pd.DataFrame, dv: str) -> pd.DataFrame:
    piv = (
        df.pivot_table(index="SubjectID", columns="Repetition", values=dv, aggfunc="mean")
        .rename(columns={1: "R1", 2: "R2"})
        .reset_index()
    )
    if "R1" not in piv.columns:
        piv["R1"] = np.nan
    if "R2" not in piv.columns:
        piv["R2"] = np.nan
    piv["diff_R2_minus_R1"] = piv["R2"] - piv["R1"]
    return piv


def main():
    ap = argparse.ArgumentParser(description="Analysis-2 Task1: within-scene stage gap (Repetition 2 - 1) for S1-S5")
    ap.add_argument("--long-csv", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, default=Path("results/research"))
    ap.add_argument("--group-col", default="PeopleGroup4", help="Grouping column (default: PeopleGroup4)")
    ap.add_argument("--min-n", type=int, default=3, help="Minimum paired subjects required to run tests")
    args = ap.parse_args()

    apply_bae_style()

    out = args.out_dir
    out.mkdir(parents=True, exist_ok=True)
    fig_dir = out / "analysis2_scene_stage_gap_figures"
    fig_dir.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(args.long_csv)

    # Basic required columns
    req = ["SubjectID", "SceneID", "Repetition"] + [c for c in DVS if c in df.columns]
    miss = [c for c in ["SubjectID", "SceneID", "Repetition"] if c not in df.columns]
    if miss:
        raise SystemExit(f"Missing required columns: {miss}")

    # group column
    df = make_people_group4(df)
    group_col = args.group_col
    if group_col not in df.columns:
        raise SystemExit(f"Missing group column: {group_col}")

    # ensure numeric
    for dv in DVS:
        if dv in df.columns:
            df[dv] = pd.to_numeric(df[dv], errors="coerce")

    # repetition numeric
    df["Repetition"] = pd.to_numeric(df["Repetition"], errors="coerce")

    scenes = sorted([s for s in df["SceneID"].dropna().unique()])
    if not scenes:
        raise SystemExit("No SceneID found in long table.")

    rows = []
    for scene in scenes:
        d_scene = df[df["SceneID"] == scene].copy()

        # only repetitions 1/2
        d_scene = d_scene[d_scene["Repetition"].isin([1, 2])]

        for g, dg in d_scene.groupby(group_col):
            for dv in DVS:
                if dv not in dg.columns:
                    continue

                pairs = _within_subject_pairs(dg[["SubjectID", "Repetition", dv]].dropna(subset=[dv]), dv)
                pairs = pairs.dropna(subset=["R1", "R2"], how="any")

                n = int(len(pairs))
                if n < args.min_n:
                    rows.append({
                        "SceneID": scene,
                        "GroupCol": group_col,
                        "Group": g,
                        "DV": dv,
                        "n_pairs": n,
                        "mean_R1": float(np.nanmean(pairs["R1"])) if n else np.nan,
                        "mean_R2": float(np.nanmean(pairs["R2"])) if n else np.nan,
                        "mean_diff_R2_minus_R1": float(np.nanmean(pairs["diff_R2_minus_R1"])) if n else np.nan,
                        "p": np.nan,
                        "p_holm": np.nan,
                        "sr": np.nan,
                        "dz": np.nan,
                        "p_t": np.nan,
                        "t": np.nan,
                    })
                    continue

                diff = pairs["diff_R2_minus_R1"].to_numpy(dtype=float)
                sign = float(np.nanmean(diff))

                # Wilcoxon signed-rank (robust p)
                try:
                    w = wilcoxon(pairs["R2"], pairs["R1"], zero_method="wilcox", correction=False, alternative="two-sided")
                    p_w = float(w.pvalue)
                except Exception:
                    p_w = np.nan

                # paired t-test (for dz + reference)
                try:
                    tt = ttest_rel(pairs["R2"], pairs["R1"], nan_policy="omit")
                    p_t = float(tt.pvalue)
                    t_stat = float(tt.statistic)
                except Exception:
                    p_t, t_stat = np.nan, np.nan

                dz = _cohens_dz(diff)
                sr = _signed_rank_r_from_p(p_w, n=n, sign=sign)

                rows.append({
                    "SceneID": scene,
                    "GroupCol": group_col,
                    "Group": g,
                    "DV": dv,
                    "n_pairs": n,
                    "mean_R1": float(np.mean(pairs["R1"])),
                    "mean_R2": float(np.mean(pairs["R2"])),
                    "mean_diff_R2_minus_R1": float(np.mean(diff)),
                    "p": p_w,
                    "p_holm": np.nan,  # fill later within scene×group
                    "sr": sr,
                    "dz": dz,
                    "p_t": p_t,
                    "t": t_stat,
                })

    out_long = pd.DataFrame(rows)

    # Holm correction within each SceneID×Group (across 5 DVs)
    from statsmodels.stats.multitest import multipletests

    out_long["p_holm"] = np.nan
    for (scene, g), sub in out_long.groupby(["SceneID", "Group"], dropna=False):
        idx = sub.index.to_list()
        pvals = out_long.loc[idx, "p"].to_numpy(dtype=float)
        ok = np.isfinite(pvals)
        if ok.sum() == 0:
            continue
        _, p_adj, _, _ = multipletests(pvals[ok], method="holm")
        out_long.loc[np.array(idx)[ok], "p_holm"] = p_adj

    out_long["sig_holm"] = out_long["p_holm"].apply(_sigstar)

    out_long_path = out / "analysis2_scene_stage_gap_long.csv"
    out_long.to_csv(out_long_path, index=False, encoding="utf-8-sig")

    # Per-scene wide tables + figures
    outputs = [str(out_long_path.relative_to(out))]

    for scene in scenes:
        sub = out_long[out_long["SceneID"] == scene].copy()
        if sub.empty:
            continue

        # build wide: one row per group, columns per DV metric
        wide_parts = []
        for metric in ["mean_diff_R2_minus_R1", "p_holm", "sr", "dz", "n_pairs"]:
            piv = sub.pivot_table(index="Group", columns="DV", values=metric, aggfunc="first")
            piv.columns = [f"{c}_{metric}" for c in piv.columns]
            wide_parts.append(piv)
        wide = pd.concat(wide_parts, axis=1).reset_index().rename(columns={"Group": group_col})

        wide_path = out / f"analysis2_scene_stage_gap_wide_{scene}.csv"
        wide.to_csv(wide_path, index=False, encoding="utf-8-sig")
        outputs.append(str(wide_path.relative_to(out)))

        # figure: heatmap of dz, annotate with p_holm
        pivot_dz = sub.pivot_table(index="Group", columns="DV", values="dz", aggfunc="first")
        pivot_p = sub.pivot_table(index="Group", columns="DV", values="p_holm", aggfunc="first")

        # enforce DV order
        pivot_dz = pivot_dz.reindex(columns=[dv for dv in DVS if dv in pivot_dz.columns])
        pivot_p = pivot_p.reindex(columns=[dv for dv in DVS if dv in pivot_p.columns])

        annot = pivot_p.copy()
        pivot_sr = sub.pivot_table(index="Group", columns="DV", values="sr", aggfunc="first")
        pivot_sr = pivot_sr.reindex(columns=[dv for dv in DVS if dv in pivot_sr.columns])

        for r in annot.index:
            for c in annot.columns:
                p = annot.loc[r, c]
                dzv = pivot_dz.loc[r, c]
                srv = pivot_sr.loc[r, c] if (r in pivot_sr.index and c in pivot_sr.columns) else np.nan
                if pd.isna(p) or pd.isna(dzv):
                    annot.loc[r, c] = ""
                else:
                    if pd.isna(srv):
                        annot.loc[r, c] = f"dz={dzv:.2f}\np={p:.3f}"
                    else:
                        annot.loc[r, c] = f"dz={dzv:.2f}\nsr={srv:.2f}\np={p:.3f}"

        plt.figure(figsize=(10, max(2.6, 0.5 * len(pivot_dz.index) + 1.2)))
        sns.heatmap(
            pivot_dz,
            cmap="vlag",
            center=0,
            annot=annot,
            fmt="",
            linewidths=0.5,
            linecolor="#dddddd",
            cbar_kws={"label": "Cohen's dz (R2 - R1)"},
        )
        plt.title(f"Scene stage gap (Repetition2 - Repetition1) — {scene} — group={group_col}\nWilcoxon p (Holm within group), dz + sr shown")
        plt.xlabel("DV")
        plt.ylabel(group_col)
        plt.tight_layout()
        fig_path = fig_dir / f"scene_{scene}.png"
        plt.savefig(fig_path, dpi=220)
        plt.close()
        outputs.append(str(fig_path.relative_to(out)))

    payload = {
        "task": "analysis-2/task1 scene stage gap",
        "group_col": group_col,
        "dvs": DVS,
        "n_scenes": len(scenes),
        "scenes": scenes,
        "out_dir": str(out),
        "outputs": outputs,
    }
    (out / "analysis2_scene_stage_gap_summary.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(payload, ensure_ascii=False))


if __name__ == "__main__":
    main()
