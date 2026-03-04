#!/usr/bin/env python3
from __future__ import annotations

"""Analysis-2 Task1b: Round2-Round1 gap for B1–B3 (C1-only items).

Rationale:
- B items (B1–B3, Bmean) are designed as C1-only (Complexity==1) manipulation-check / supplementary.
- We compute within-subject gap between Repetition=2 and Repetition=1.
- Stratify by people group (default PeopleGroup4 = Experience×SportFreq).
- Provide p (Wilcoxon signed-rank), sr (signed-rank r approx), dz (paired Cohen's dz).
- Produce 3 PNGs total (B1, B2, B3): per-group mean diff with p/dz annotation.

Outputs (under out-dir, default results/research):
- analysis2_b_stage_gap_long.csv
- task1b_b_stage_gap_figures/B1.png, B2.png, B3.png
- analysis2_b_stage_gap_summary.json
"""

from pathlib import Path
import argparse
import json

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy.stats import ttest_rel, wilcoxon, norm

from analysis_groups import make_people_group4
from plot_style import apply_bae_style


B_DVS = ["B1", "B2", "B3"]


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
    p = float(max(min(float(p), 1.0), 1e-300))
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


def _pairs(df: pd.DataFrame, dv: str) -> pd.DataFrame:
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


def _exclude_subjects(df: pd.DataFrame, text: str) -> pd.DataFrame:
    if not text:
        return df
    names = [x.strip() for x in str(text).split(",") if x.strip()]
    if not names or "SubjectID" not in df.columns:
        return df
    sid = df["SubjectID"].astype(str).str.strip()
    return df.loc[~sid.isin(set(names))].copy()


def main():
    ap = argparse.ArgumentParser(description="Analysis-2 Task1b: B1-B3 Round2-Round1 gap by people group (C1-only)")
    ap.add_argument("--long-csv", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, default=Path("results/research"))
    ap.add_argument("--group-col", default="PeopleGroup4")
    ap.add_argument("--min-n", type=int, default=3)
    ap.add_argument("--exclude-subjects", default="", help="Comma-separated SubjectID list for QC exclusion")
    args = ap.parse_args()

    apply_bae_style()

    out = args.out_dir
    out.mkdir(parents=True, exist_ok=True)
    fig_dir = out / "task1b_b_stage_gap_figures"
    fig_dir.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(args.long_csv)
    df = _exclude_subjects(df, args.exclude_subjects)

    for c in ["SubjectID", "Repetition"]:
        if c not in df.columns:
            raise SystemExit(f"Missing required column: {c}")

    # Ensure group col exists
    df = make_people_group4(df)
    if args.group_col not in df.columns:
        raise SystemExit(f"Missing group column: {args.group_col}")

    # B items must be C1-only (Complexity==1) when present
    if "Complexity" in df.columns:
        for dv in B_DVS:
            if dv in df.columns:
                bad = df[(df["Complexity"] != 1) & (pd.to_numeric(df[dv], errors="coerce").notna())]
                if len(bad) > 0:
                    raise SystemExit(f"Found non-NA {dv} values in Complexity!=1 rows. This violates design (B items are C1-only).")
        df = df[df["Complexity"] == 1].copy()

    # keep only Repetition 1/2
    df["Repetition"] = pd.to_numeric(df["Repetition"], errors="coerce")
    df = df[df["Repetition"].isin([1, 2])].copy()

    for dv in B_DVS:
        if dv in df.columns:
            df[dv] = pd.to_numeric(df[dv], errors="coerce")

    rows = []

    for g, dg in df.groupby(args.group_col):
        for dv in B_DVS:
            if dv not in dg.columns:
                continue

            pairs = _pairs(dg[["SubjectID", "Repetition", dv]].dropna(subset=[dv]), dv)
            pairs = pairs.dropna(subset=["R1", "R2"], how="any")
            n = int(len(pairs))

            if n < args.min_n:
                rows.append({
                    "GroupCol": args.group_col,
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

            try:
                w = wilcoxon(pairs["R2"], pairs["R1"], zero_method="wilcox", correction=False, alternative="two-sided")
                p_w = float(w.pvalue)
            except Exception:
                p_w = np.nan

            try:
                tt = ttest_rel(pairs["R2"], pairs["R1"], nan_policy="omit")
                p_t = float(tt.pvalue)
                t_stat = float(tt.statistic)
            except Exception:
                p_t, t_stat = np.nan, np.nan

            rows.append({
                "GroupCol": args.group_col,
                "Group": g,
                "DV": dv,
                "n_pairs": n,
                "mean_R1": float(np.mean(pairs["R1"])),
                "mean_R2": float(np.mean(pairs["R2"])),
                "mean_diff_R2_minus_R1": float(np.mean(diff)),
                "p": p_w,
                "p_holm": np.nan,
                "sr": _signed_rank_r_from_p(p_w, n=n, sign=sign),
                "dz": _cohens_dz(diff),
                "p_t": p_t,
                "t": t_stat,
            })

    out_long = pd.DataFrame(rows)

    # Holm within each group across B1-B3
    from statsmodels.stats.multitest import multipletests

    out_long["p_holm"] = np.nan
    for g, sub in out_long.groupby(["Group"], dropna=False):
        idx = sub.index.to_list()
        pvals = out_long.loc[idx, "p"].to_numpy(dtype=float)
        ok = np.isfinite(pvals)
        if ok.sum() == 0:
            continue
        _, p_adj, _, _ = multipletests(pvals[ok], method="holm")
        out_long.loc[np.array(idx)[ok], "p_holm"] = p_adj

    out_long["sig_holm"] = out_long["p_holm"].apply(_sigstar)

    out_path = out / "analysis2_b_stage_gap_long.csv"
    out_long.to_csv(out_path, index=False, encoding="utf-8-sig")

    # Figures: 3 pngs total (B1/B2/B3): per-group mean diff bar plot
    groups = list(out_long["Group"].dropna().unique())
    groups = sorted(groups)

    for dv in B_DVS:
        sub = out_long[out_long["DV"] == dv].copy()
        if sub.empty:
            continue
        sub = sub.set_index("Group").reindex(groups).reset_index()

        y = np.arange(len(sub))
        x = sub["mean_diff_R2_minus_R1"].to_numpy(dtype=float)

        plt.figure(figsize=(10, max(2.6, 0.45 * len(sub) + 1.2)))
        plt.axvline(0, color="#666666", linewidth=1)
        plt.barh(y, x, color="#4c78a8", alpha=0.85)
        plt.yticks(y, sub["Group"].astype(str))
        plt.xlabel("Mean diff (Round2 - Round1)")
        plt.title(f"B item stage gap by group (C1-only): {dv}\nWilcoxon p (Holm within group), dz + sr shown")

        # annotate p/dz
        for i, row in sub.iterrows():
            p = row.get("p_holm")
            dz = row.get("dz")
            sr = row.get("sr")
            n = row.get("n_pairs")
            if pd.isna(p) or pd.isna(dz) or pd.isna(row.get("mean_diff_R2_minus_R1")):
                txt = f"n={int(n) if pd.notna(n) else 0}"
            else:
                if pd.isna(sr):
                    txt = f"n={int(n)}  p={p:.3f}  dz={dz:.2f}{row.get('sig_holm','')}"
                else:
                    txt = f"n={int(n)}  p={p:.3f}  dz={dz:.2f}  sr={sr:.2f}{row.get('sig_holm','')}"
            xx = row["mean_diff_R2_minus_R1"]
            if pd.isna(xx):
                xx = 0
            plt.text(xx + (0.02 if xx >= 0 else -0.02), i, txt, va="center", ha="left" if xx >= 0 else "right", fontsize=9)

        plt.tight_layout()
        fig_path = fig_dir / f"{dv}.png"
        plt.savefig(fig_path, dpi=220)
        plt.close()

    payload = {
        "task": "analysis-2/task1b b-item stage gap",
        "group_col": args.group_col,
        "dvs": B_DVS,
        "out_dir": str(out),
        "outputs": [
            str(out_path.relative_to(out)),
            str((fig_dir / "B1.png").relative_to(out)) if (fig_dir / "B1.png").exists() else None,
            str((fig_dir / "B2.png").relative_to(out)) if (fig_dir / "B2.png").exists() else None,
            str((fig_dir / "B3.png").relative_to(out)) if (fig_dir / "B3.png").exists() else None,
        ],
    }
    payload["outputs"] = [p for p in payload["outputs"] if p]
    (out / "analysis2_b_stage_gap_summary.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(payload, ensure_ascii=False))


if __name__ == "__main__":
    main()
