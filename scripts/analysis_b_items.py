#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import argparse
import json
import numpy as np
import pandas as pd
from scipy.stats import ttest_ind
from statsmodels.stats.multitest import multipletests

from analysis_groups import make_people_group4


def _sigstar(p):
    if pd.isna(p):
        return ""
    if p < 0.001:
        return "***"
    if p < 0.01:
        return "**"
    if p < 0.05:
        return "*"
    return ""


def main():
    ap = argparse.ArgumentParser(description="B-item analysis (B1-B3/Bmean), mainly C1")
    ap.add_argument("--long-csv", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, default=Path("results/research"))
    args = ap.parse_args()

    out = args.out_dir
    out.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(args.long_csv)
    if "ExperienceGroup" not in df.columns:
        df["ExperienceGroup"] = "Unknown"
    if "SportFreqGroup" not in df.columns:
        df["SportFreqGroup"] = "Unknown"
    if "Repetition" not in df.columns:
        df["Repetition"] = df["Block"] if "Block" in df.columns else np.nan
    if "Complexity" in df.columns:
        df["Complexity"] = pd.to_numeric(df["Complexity"], errors="coerce")

    df = make_people_group4(df)

    b_cols = [c for c in ["B1", "B2", "B3", "Bmean"] if c in df.columns]
    if not b_cols:
        payload = {"outputs": [], "message": "No B columns found."}
        (out / "b_items_summary.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(payload, ensure_ascii=False))
        return

    bdf = df[df["Complexity"] == 1].copy() if "Complexity" in df.columns else df.copy()
    bdf = bdf.dropna(subset=["SubjectID", "WWR", "Repetition", "ExperienceGroup", "SportFreqGroup"], how="any")
    b_long = bdf.melt(
        id_vars=["SubjectID", "WWR", "Repetition", "ExperienceGroup", "SportFreqGroup", "PeopleGroup4"],
        value_vars=b_cols,
        var_name="B_Item",
        value_name="Score",
    ).dropna(subset=["Score"])
    b_long.to_csv(out / "b_items_long_c1.csv", index=False, encoding="utf-8-sig")

    b_means = (
        b_long.groupby(["B_Item", "PeopleGroup4", "ExperienceGroup", "SportFreqGroup", "WWR", "Repetition"], dropna=False)["Score"]
        .agg(n="count", mean="mean", sd="std")
        .reset_index()
    )
    b_means.to_csv(out / "b_items_condition_means.csv", index=False, encoding="utf-8-sig")

    rows = []
    groups = sorted(b_long["PeopleGroup4"].dropna().unique())
    for bi in sorted(b_long["B_Item"].dropna().unique()):
        subj = b_long[b_long["B_Item"] == bi].groupby(["SubjectID", "PeopleGroup4"], as_index=False)["Score"].mean()
        pvals, tmp = [], []
        for i in range(len(groups)):
            for j in range(i + 1, len(groups)):
                g1, g2 = groups[i], groups[j]
                v1 = subj.loc[subj["PeopleGroup4"] == g1, "Score"].dropna().to_numpy(dtype=float)
                v2 = subj.loc[subj["PeopleGroup4"] == g2, "Score"].dropna().to_numpy(dtype=float)
                if len(v1) < 3 or len(v2) < 3:
                    t, p = np.nan, np.nan
                else:
                    r = ttest_ind(v1, v2, equal_var=False, nan_policy="omit")
                    t, p = float(r.statistic), float(r.pvalue)
                pvals.append(p)
                tmp.append((g1, g2, len(v1), len(v2), np.mean(v1) if len(v1) else np.nan, np.mean(v2) if len(v2) else np.nan, t, p))

        valid = np.isfinite(pvals)
        p_adj = [np.nan] * len(pvals)
        if np.any(valid):
            _, corr, _, _ = multipletests(np.array(pvals)[valid], method="holm")
            k = 0
            for idx, ok in enumerate(valid):
                if ok:
                    p_adj[idx] = float(corr[k])
                    k += 1

        for (g1, g2, n1, n2, m1, m2, t, p), ph in zip(tmp, p_adj):
            rows.append({
                "B_Item": bi,
                "GroupA": g1,
                "GroupB": g2,
                "nA_subjects": n1,
                "nB_subjects": n2,
                "meanA": m1,
                "meanB": m2,
                "delta_A_minus_B": (m1 - m2) if pd.notna(m1) and pd.notna(m2) else np.nan,
                "t_welch": t,
                "p": p,
                "p_holm": ph,
                "sig_holm": _sigstar(ph),
            })

    b_cmp_df = pd.DataFrame(rows)
    b_cmp_df.to_csv(out / "b_items_group_comparisons.csv", index=False, encoding="utf-8-sig")

    payload = {
        "outputs": [
            "b_items_long_c1.csv",
            "b_items_condition_means.csv",
            "b_items_group_comparisons.csv",
        ]
    }
    (out / "b_items_summary.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False))


if __name__ == "__main__":
    main()
