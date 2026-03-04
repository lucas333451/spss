#!/usr/bin/env python3
from __future__ import annotations

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

S_DVS = ["S1", "S2", "S3", "S4", "S5"]


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
    if n <= 0 or pd.isna(p):
        return np.nan
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


def _exclude_subjects(df: pd.DataFrame, text: str) -> pd.DataFrame:
    if not text:
        return df
    names = [x.strip() for x in str(text).split(",") if x.strip()]
    if not names or "SubjectID" not in df.columns:
        return df
    sid = df["SubjectID"].astype(str).str.strip()
    return df.loc[~sid.isin(set(names))].copy()


def _pairs_complexity(df: pd.DataFrame, dv: str) -> pd.DataFrame:
    piv = (
        df.pivot_table(index="SubjectID", columns="Complexity", values=dv, aggfunc="mean")
        .rename(columns={0: "C0", 1: "C1"})
        .reset_index()
    )
    if "C0" not in piv.columns:
        piv["C0"] = np.nan
    if "C1" not in piv.columns:
        piv["C1"] = np.nan
    piv["diff_C1_minus_C0"] = piv["C1"] - piv["C0"]
    return piv


def _plot_p_heatmap(df_long: pd.DataFrame, out_png: Path) -> bool:
    if df_long.empty:
        return False
    x = df_long.copy()
    x["Cell"] = x["DV"].astype(str) + " | R" + x["Repetition"].astype(str)
    mat = x.pivot_table(index="Group", columns="Cell", values="p_holm", aggfunc="first")
    if mat.empty:
        return False

    annot = mat.copy().astype(object)
    for r in annot.index:
        for c in annot.columns:
            p = annot.loc[r, c]
            if pd.isna(p):
                annot.loc[r, c] = ""
            else:
                pv = float(p)
                ptxt = f"{pv:.3f}".lstrip("0")
                annot.loc[r, c] = f"p{ptxt}{_sigstar(pv)}"

    plt.figure(figsize=(max(11, 0.9 * len(mat.columns) + 3), max(3.0, 0.58 * len(mat.index) + 1.2)))
    sns.heatmap(
        -np.log10(mat.astype(float)),
        cmap="Blues",
        annot=annot,
        fmt="",
        annot_kws={"fontsize": 9},
        linewidths=0.6,
        linecolor="#efefef",
        cbar_kws={"label": "-log10(p_holm)"},
    )
    plt.title("Task4 complexity-gap significance map by Group × (DV,Round)")
    plt.xlabel("DV | Round")
    plt.ylabel("Group")
    plt.xticks(rotation=25, ha="right")
    plt.tight_layout()
    out_png.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_png, dpi=230)
    plt.close()
    return True


def _plot_dz_rank(df_long: pd.DataFrame, out_png: Path, top_n: int = 20) -> bool:
    if df_long.empty or "dz" not in df_long.columns:
        return False
    x = df_long.dropna(subset=["dz"]).copy()
    if x.empty:
        return False
    x["abs_dz"] = x["dz"].abs()
    x["Label"] = x["DV"].astype(str) + " | R" + x["Repetition"].astype(str) + " | " + x["Group"].astype(str)
    x = x.sort_values("abs_dz", ascending=False).head(top_n).sort_values("dz")

    plt.figure(figsize=(10, max(3.2, 0.34 * len(x) + 1.5)))
    plt.axvline(0, color="#666", lw=1)
    plt.barh(np.arange(len(x)), x["dz"], color="#4E79A7")
    plt.yticks(np.arange(len(x)), x["Label"].astype(str), fontsize=8)
    plt.xlabel("Cohen's dz (C1 - C0)")
    plt.title("Task4 strongest complexity effects (|dz| rank)")
    plt.tight_layout()
    out_png.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_png, dpi=230)
    plt.close()
    return True


def main():
    ap = argparse.ArgumentParser(description="Analysis-2 Task4: Complexity gap (C1-C0) for S1-S5 by round and group")
    ap.add_argument("--long-csv", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, default=Path("results/research"))
    ap.add_argument("--group-col", default="PeopleGroup4")
    ap.add_argument("--min-n", type=int, default=3)
    ap.add_argument("--exclude-subjects", default="", help="Comma-separated SubjectID list for QC exclusion")
    args = ap.parse_args()

    apply_bae_style()

    out = args.out_dir
    out.mkdir(parents=True, exist_ok=True)
    fig_dir = out / "task4_complexity_gap_figures"
    fig_dir.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(args.long_csv)
    df = _exclude_subjects(df, args.exclude_subjects)

    for c in ["SubjectID", "Complexity", "Repetition"]:
        if c not in df.columns:
            raise SystemExit(f"Missing required column: {c}")

    if args.group_col == "PeopleGroup4" and "PeopleGroup4" not in df.columns:
        df = make_people_group4(df)
    if args.group_col not in df.columns:
        raise SystemExit(f"Missing group column: {args.group_col}")

    df["Repetition"] = pd.to_numeric(df["Repetition"], errors="coerce")
    df["Complexity"] = pd.to_numeric(df["Complexity"], errors="coerce")

    rows = []

    for dv in S_DVS:
        if dv not in df.columns:
            continue
        sub = df.dropna(subset=["SubjectID", args.group_col, "Repetition", "Complexity", dv]).copy()
        if sub.empty:
            continue

        for (g, r), sg in sub.groupby([args.group_col, "Repetition"], dropna=False):
            pairs = _pairs_complexity(sg[["SubjectID", "Complexity", dv]].copy(), dv)
            pairs = pairs.dropna(subset=["C0", "C1"], how="any")

            n = int(len(pairs))
            if n < args.min_n:
                rows.append({
                    "DV": dv,
                    "Group": g,
                    "Repetition": r,
                    "n_pairs": n,
                    "mean_C0": float(np.nanmean(pairs["C0"])) if n else np.nan,
                    "mean_C1": float(np.nanmean(pairs["C1"])) if n else np.nan,
                    "mean_diff_C1_minus_C0": float(np.nanmean(pairs["diff_C1_minus_C0"])) if n else np.nan,
                    "p": np.nan,
                    "dz": np.nan,
                    "sr": np.nan,
                })
                continue

            diff = pairs["diff_C1_minus_C0"].to_numpy(dtype=float)
            sign = float(np.nanmean(diff))

            if np.isfinite(diff).sum() == 0:
                p_w = np.nan
            elif np.allclose(diff[np.isfinite(diff)], 0.0):
                p_w = 1.0
            else:
                try:
                    w = wilcoxon(diff, zero_method="wilcox", correction=False, alternative="two-sided")
                    p_w = float(w.pvalue) if np.isfinite(w.pvalue) else 1.0
                except Exception:
                    p_w = np.nan

            dz = _cohens_dz(diff)
            n_eff = int(np.sum(np.isfinite(diff) & (np.abs(diff) > 0)))
            sr = _signed_rank_r_from_p(p_w, n=max(n_eff, 1), sign=sign)

            rows.append({
                "DV": dv,
                "Group": g,
                "Repetition": r,
                "n_pairs": n,
                "mean_C0": float(np.mean(pairs["C0"])),
                "mean_C1": float(np.mean(pairs["C1"])),
                "mean_diff_C1_minus_C0": float(np.mean(diff)),
                "p": p_w,
                "dz": dz,
                "sr": sr,
            })

    out_long = pd.DataFrame(rows)

    # Holm within each Group x Repetition over 5 DVs
    from statsmodels.stats.multitest import multipletests

    out_long["p_holm"] = np.nan
    for (g, r), sub in out_long.groupby(["Group", "Repetition"], dropna=False):
        idx = sub.index.to_list()
        pvals = out_long.loc[idx, "p"].to_numpy(dtype=float)
        ok = np.isfinite(pvals)
        if ok.sum() == 0:
            continue
        _, p_adj, _, _ = multipletests(pvals[ok], method="holm")
        out_long.loc[np.array(idx)[ok], "p_holm"] = p_adj
    out_long["sig_holm"] = out_long["p_holm"].apply(_sigstar)

    out_path = out / "analysis2_task4_complexity_gap_long.csv"
    out_long.to_csv(out_path, index=False, encoding="utf-8-sig")

    outputs = [str(out_path.relative_to(out))]

    # one heatmap per round
    rounds = sorted([r for r in out_long["Repetition"].dropna().unique()])
    for r in rounds:
        sub = out_long[out_long["Repetition"] == r].copy()
        if sub.empty:
            continue

        mat = sub.pivot_table(index="Group", columns="DV", values="mean_diff_C1_minus_C0", aggfunc="first")
        pmat = sub.pivot_table(index="Group", columns="DV", values="p_holm", aggfunc="first")
        dzmat = sub.pivot_table(index="Group", columns="DV", values="dz", aggfunc="first")

        mat = mat.reindex(columns=[dv for dv in S_DVS if dv in mat.columns])
        pmat = pmat.reindex(index=mat.index, columns=mat.columns)
        dzmat = dzmat.reindex(index=mat.index, columns=mat.columns)

        annot = pmat.copy().astype(object)
        for rr in annot.index:
            for cc in annot.columns:
                p = annot.loc[rr, cc]
                dlt = mat.loc[rr, cc]
                dz = dzmat.loc[rr, cc]
                if pd.isna(dlt) or pd.isna(p):
                    annot.loc[rr, cc] = ""
                else:
                    annot.loc[rr, cc] = f"p={p:.3f}{_sigstar(float(p))}\nΔ={dlt:.2f}\ndz={dz:.2f}" if pd.notna(dz) else f"p={p:.3f}{_sigstar(float(p))}\nΔ={dlt:.2f}"

        plt.figure(figsize=(10, max(2.8, 0.5 * len(mat.index) + 1.2)))
        sns.heatmap(
            mat,
            cmap="vlag",
            center=0,
            annot=annot,
            fmt="",
            linewidths=0.6,
            linecolor="#efefef",
            cbar_kws={"label": "Δ mean (C1 - C0)"},
        )
        plt.title(f"Task4 Complexity gap by group | Round {int(r)}")
        plt.xlabel("DV")
        plt.ylabel(args.group_col)
        plt.tight_layout()
        p = fig_dir / f"task4_complexity_gap_round{int(r)}.png"
        plt.savefig(p, dpi=230)
        plt.close()
        outputs.append(str(p.relative_to(out)))

    pmap_png = fig_dir / "task4_complexity_gap_p_heatmap.png"
    if _plot_p_heatmap(out_long, pmap_png):
        outputs.append(str(pmap_png.relative_to(out)))

    dz_png = fig_dir / "task4_complexity_gap_dz_rank.png"
    if _plot_dz_rank(out_long, dz_png):
        outputs.append(str(dz_png.relative_to(out)))

    payload = {
        "task": "analysis-2/task4 complexity gap",
        "group_col": args.group_col,
        "dvs": [dv for dv in S_DVS if dv in df.columns],
        "outputs": outputs,
        "notes": [
            "Within-subject C1-C0 contrasts by round and group.",
            "Holm correction applied within each Group×Round across S1-S5.",
        ],
    }
    (out / "analysis2_task4_complexity_gap_summary.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False))


if __name__ == "__main__":
    main()
