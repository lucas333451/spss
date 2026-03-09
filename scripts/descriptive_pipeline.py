#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import argparse
import json

import numpy as np
import pandas as pd

QC_EXCLUDE = "孙校聪,康少勇,张钰鹏,杨可,洪婷婷,陈韬,高梓楠,赵国宏"
S_COLS = ["S1", "S2", "S3", "S4", "S5"]
B_COLS = ["B1", "B2", "B3", "Bmean"]
IPQ_COLS = ["IPQ1", "IPQ2", "IPQ3", "IPQ4", "IPQ5", "IPQ6", "IPQ_mean"]


def _exclude_subjects(df: pd.DataFrame, text: str) -> pd.DataFrame:
    if not text or "SubjectID" not in df.columns:
        return df
    names = [x.strip() for x in str(text).split(",") if x.strip()]
    if not names:
        return df
    sid = df["SubjectID"].astype(str).str.strip()
    return df.loc[~sid.isin(set(names))].copy()


def _desc_table(df: pd.DataFrame, cols: list[str], group_col: str | None = None) -> pd.DataFrame:
    rows = []
    use_cols = [c for c in cols if c in df.columns]
    if not use_cols:
        return pd.DataFrame()

    if group_col and group_col in df.columns:
        groups = list(df[group_col].dropna().unique())
        iter_items = [(g, df[df[group_col] == g].copy()) for g in groups]
    else:
        iter_items = [("ALL", df.copy())]
        group_col = "Group"

    for g, sub in iter_items:
        for c in use_cols:
            z = pd.to_numeric(sub[c], errors="coerce")
            n = int(z.notna().sum())
            rows.append({
                group_col: g,
                "DV": c,
                "n": n,
                "mean": float(z.mean()) if n else np.nan,
                "sd": float(z.std(ddof=1)) if n > 1 else np.nan,
                "median": float(z.median()) if n else np.nan,
                "min": float(z.min()) if n else np.nan,
                "max": float(z.max()) if n else np.nan,
            })
    out = pd.DataFrame(rows)
    return out


def main():
    ap = argparse.ArgumentParser(description="Descriptive-only pipeline: overall + experience")
    ap.add_argument("--long-csv", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, default=Path("results/descriptive"))
    ap.add_argument("--with-qc", action="store_true", help="Also export QC-excluded outputs")
    args = ap.parse_args()

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
        s_overall = _desc_table(x, S_COLS)
        b_overall = _desc_table(x[x["Complexity"].astype(str).isin(["1", "1.0"])].copy() if "Complexity" in x.columns else x, B_COLS)
        ipq_overall = _desc_table(x.groupby("SubjectID", as_index=False).first() if "SubjectID" in x.columns else x, IPQ_COLS)
        s_overall.to_csv(overall_dir / "s1_s5_descriptives.csv", index=False, encoding="utf-8-sig")
        b_overall.to_csv(overall_dir / "b1_b3_descriptives.csv", index=False, encoding="utf-8-sig")
        ipq_overall.to_csv(overall_dir / "ipq_descriptives.csv", index=False, encoding="utf-8-sig")
        outputs += [
            str((overall_dir / "s1_s5_descriptives.csv").relative_to(out)),
            str((overall_dir / "b1_b3_descriptives.csv").relative_to(out)),
            str((overall_dir / "ipq_descriptives.csv").relative_to(out)),
        ]

        if "ExperienceGroup" in x.columns:
            exp_dir = base / "experience"
            exp_dir.mkdir(parents=True, exist_ok=True)
            s_exp = _desc_table(x, S_COLS, "ExperienceGroup")
            b_exp = _desc_table(x[x["Complexity"].astype(str).isin(["1", "1.0"])].copy() if "Complexity" in x.columns else x, B_COLS, "ExperienceGroup")
            ipq_subj = x.groupby("SubjectID", as_index=False).first() if "SubjectID" in x.columns else x
            ipq_exp = _desc_table(ipq_subj, IPQ_COLS, "ExperienceGroup")
            s_exp.to_csv(exp_dir / "s1_s5_descriptives_by_experience.csv", index=False, encoding="utf-8-sig")
            b_exp.to_csv(exp_dir / "b1_b3_descriptives_by_experience.csv", index=False, encoding="utf-8-sig")
            ipq_exp.to_csv(exp_dir / "ipq_descriptives_by_experience.csv", index=False, encoding="utf-8-sig")
            outputs += [
                str((exp_dir / "s1_s5_descriptives_by_experience.csv").relative_to(out)),
                str((exp_dir / "b1_b3_descriptives_by_experience.csv").relative_to(out)),
                str((exp_dir / "ipq_descriptives_by_experience.csv").relative_to(out)),
            ]

    payload = {
        "task": "descriptive pipeline",
        "scope": ["overall", "experience"],
        "branches": [b for b, _ in branches],
        "outputs": outputs,
    }
    (out / "descriptive_summary.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False))


if __name__ == "__main__":
    main()
