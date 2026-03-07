#!/usr/bin/env python3
from __future__ import annotations

"""Analyze participant-level IPQ items (Q16.1_1..Q16.6_1) from long-format data.

Design notes
- IPQ items are participant-level (one row per subject) but are repeated across 12 long rows.
- Therefore we aggregate to subject-level before any inferential statistics.

Outputs (under out-dir; default results/ipq):
- ipq_subject_level.csv
- ipq_descriptives.csv
- ipq_reliability.csv
- ipq_group_comparisons.csv
- ipq_lmm.csv (optional; exploratory)
- ipq_report_zh.md

Interpretation
- Primary reporting should use descriptives + group comparisons (ExperienceGroup / SportFreqGroup).
- LMM on IPQ_mean is optional and should be treated as exploratory because predictors like WWR/Complexity
  are within-subject trial factors (not meaningful for participant-level IPQ).
"""

from pathlib import Path
import argparse
import json

import numpy as np
import pandas as pd
import pingouin as pg
from scipy.stats import ttest_ind
from statsmodels.stats.multitest import multipletests


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


def _cronbach_alpha(df_items: pd.DataFrame) -> float:
    x = df_items.dropna()
    if x.shape[0] < 3 or x.shape[1] < 2:
        return np.nan
    return float(pg.cronbach_alpha(data=x)[0])


def _subject_level(df_long: pd.DataFrame, ipq_cols: list[str]) -> pd.DataFrame:
    keep = ["SubjectID", "ExperienceGroup", "SportFreqGroup"] + ipq_cols
    miss = [c for c in keep if c not in df_long.columns]
    if miss:
        raise SystemExit(f"Missing columns in long CSV: {miss}")

    x = df_long[keep].copy()
    x["SubjectID"] = x["SubjectID"].astype(str).str.strip()

    # Aggregate to one row per subject (use mean in case of duplicates; should be identical across 12 rows)
    agg = {c: "mean" for c in ipq_cols}
    agg.update({"ExperienceGroup": "first", "SportFreqGroup": "first"})

    out = x.groupby("SubjectID", as_index=False).agg(agg)

    arr = out[ipq_cols].to_numpy(dtype=float)
    out["IPQ_n_valid"] = np.isfinite(arr).sum(axis=1)
    out["IPQ_mean"] = np.nanmean(arr, axis=1)
    return out


def _group_pairwise(df: pd.DataFrame, group_col: str, dv: str) -> pd.DataFrame:
    x = df.dropna(subset=[group_col, dv]).copy()
    groups = sorted(x[group_col].astype(str).unique())

    rows, pvals = [], []
    for i in range(len(groups)):
        for j in range(i + 1, len(groups)):
            g1, g2 = groups[i], groups[j]
            v1 = x.loc[x[group_col].astype(str) == g1, dv].to_numpy(dtype=float)
            v2 = x.loc[x[group_col].astype(str) == g2, dv].to_numpy(dtype=float)
            v1 = v1[np.isfinite(v1)]
            v2 = v2[np.isfinite(v2)]

            if len(v1) < 3 or len(v2) < 3:
                t, p = np.nan, np.nan
            else:
                r = ttest_ind(v1, v2, equal_var=False, nan_policy="omit")
                t, p = float(r.statistic), float(r.pvalue)

            pvals.append(p)
            rows.append({
                "GroupCol": group_col,
                "DV": dv,
                "GroupA": g1,
                "GroupB": g2,
                "nA": int(len(v1)),
                "nB": int(len(v2)),
                "meanA": float(np.mean(v1)) if len(v1) else np.nan,
                "meanB": float(np.mean(v2)) if len(v2) else np.nan,
                "t_welch": t,
                "p": p,
            })

    valid = np.isfinite(pvals)
    p_adj = [np.nan] * len(pvals)
    if np.any(valid):
        _, corr, _, _ = multipletests(np.array(pvals)[valid], method="holm")
        k = 0
        for idx, ok in enumerate(valid):
            if ok:
                p_adj[idx] = float(corr[k])
                k += 1

    for i in range(len(rows)):
        rows[i]["p_holm"] = p_adj[i]
        rows[i]["sig_holm"] = _sigstar(p_adj[i])

    out = pd.DataFrame(rows)
    if not out.empty:
        out = out.sort_values(["p_holm", "p"], na_position="last").reset_index(drop=True)
    return out


def main():
    ap = argparse.ArgumentParser(description="Analyze IPQ (Q16.*) participant-level items")
    ap.add_argument("--long-csv", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, default=Path("results/ipq"))
    args = ap.parse_args()

    out = args.out_dir
    out.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(args.long_csv)

    ipq_cols = [f"IPQ{i}" for i in range(1, 7) if f"IPQ{i}" in df.columns]
    if len(ipq_cols) < 2:
        raise SystemExit(f"IPQ columns not found in long CSV. Expected IPQ1..IPQ6. Found: {ipq_cols}")

    subj = _subject_level(df, ipq_cols)
    subj.to_csv(out / "ipq_subject_level.csv", index=False, encoding="utf-8-sig")

    # Descriptives
    desc = []
    for dv in ipq_cols + ["IPQ_mean"]:
        z = subj[dv].to_numpy(dtype=float)
        desc.append({
            "DV": dv,
            "n": int(np.isfinite(z).sum()),
            "mean": float(np.nanmean(z)) if np.isfinite(z).sum() else np.nan,
            "sd": float(np.nanstd(z, ddof=1)) if np.isfinite(z).sum() > 1 else np.nan,
            "min": float(np.nanmin(z)) if np.isfinite(z).sum() else np.nan,
            "max": float(np.nanmax(z)) if np.isfinite(z).sum() else np.nan,
        })
    desc_df = pd.DataFrame(desc)
    desc_df.to_csv(out / "ipq_descriptives.csv", index=False, encoding="utf-8-sig")

    # Reliability
    alpha = _cronbach_alpha(subj[ipq_cols])
    rel = pd.DataFrame([{
        "Scale": "IPQ6",
        "k_items": int(len(ipq_cols)),
        "cronbach_alpha": alpha,
        "note": "Computed on subject-level rows; listwise deletion.",
    }])
    rel.to_csv(out / "ipq_reliability.csv", index=False, encoding="utf-8-sig")

    # Group comparisons (between-subject)
    gcmp = pd.concat([
        _group_pairwise(subj, "ExperienceGroup", "IPQ_mean"),
        _group_pairwise(subj, "SportFreqGroup", "IPQ_mean"),
    ], ignore_index=True)
    gcmp.to_csv(out / "ipq_group_comparisons.csv", index=False, encoding="utf-8-sig")

    # Simple markdown report (ZH)
    lines = []
    lines.append("# IPQ（Q16.1–Q16.6）结果汇总（自动生成）")
    lines.append("")
    lines.append("## 数据处理说明")
    lines.append("- IPQ 属于被试层面量表（每个被试一次）。long-format 中会在 12 行内重复，因此本脚本先聚合到 SubjectID 级别再做统计。")
    lines.append(f"- 使用条目：{', '.join(ipq_cols)}；并计算 IPQ_mean（条目均值）。")
    lines.append("")
    lines.append("## 描述统计")
    lines.append(desc_df.to_markdown(index=False, floatfmt=".3f"))
    lines.append("")
    lines.append("## 信度")
    lines.append(rel.to_markdown(index=False, floatfmt=".3f"))
    lines.append("")
    lines.append("## 组间比较（Welch t；Holm 校正）")
    lines.append(gcmp.to_markdown(index=False, floatfmt=".4f"))
    (out / "ipq_report_zh.md").write_text("\n".join(lines), encoding="utf-8")

    payload = {
        "out_dir": str(out),
        "ipq_cols": ipq_cols,
        "n_subjects": int(subj["SubjectID"].nunique()),
        "outputs": [
            "ipq_subject_level.csv",
            "ipq_descriptives.csv",
            "ipq_reliability.csv",
            "ipq_group_comparisons.csv",
            "ipq_report_zh.md",
        ],
    }
    (out / "ipq_summary.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False))


if __name__ == "__main__":
    main()
