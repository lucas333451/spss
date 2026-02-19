#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import numpy as np
import pandas as pd
from scipy.stats import ttest_ind
from statsmodels.stats.multitest import multipletests


def sigstar(p):
    if pd.isna(p):
        return ""
    if p < 0.001:
        return "***"
    if p < 0.01:
        return "**"
    if p < 0.05:
        return "*"
    return ""


def make_people_group4(df: pd.DataFrame) -> pd.DataFrame:
    x = df.copy()
    x["PeopleGroup4"] = x["ExperienceGroup"].astype(str) + "__" + x["SportFreqGroup"].astype(str)
    return x


def split_tables_by_people_group(df: pd.DataFrame, out_dir: Path) -> pd.DataFrame:
    out_dir.mkdir(parents=True, exist_ok=True)
    x = make_people_group4(df)

    manifest_rows = []
    for grp, g in x.groupby("PeopleGroup4", dropna=False):
        safe = str(grp).replace("/", "_").replace(" ", "")
        f = out_dir / f"group_{safe}.csv"
        g.to_csv(f, index=False, encoding="utf-8-sig")
        manifest_rows.append({
            "PeopleGroup4": grp,
            "ExperienceGroup": g["ExperienceGroup"].iloc[0],
            "SportFreqGroup": g["SportFreqGroup"].iloc[0],
            "n_rows": int(len(g)),
            "n_subjects": int(g["SubjectID"].nunique()) if "SubjectID" in g.columns else np.nan,
            "file": str(f),
        })

    m = pd.DataFrame(manifest_rows)
    m.to_csv(out_dir / "manifest.csv", index=False, encoding="utf-8-sig")
    return m


def compare_people_groups_subject_mean(df: pd.DataFrame, dv: str) -> pd.DataFrame:
    x = make_people_group4(df)
    groups = sorted(x["PeopleGroup4"].dropna().unique())

    subj = (
        x.dropna(subset=[dv, "SubjectID", "PeopleGroup4"])
        .groupby(["SubjectID", "PeopleGroup4"], as_index=False)[dv]
        .mean()
    )

    pvals, rows = [], []
    for i in range(len(groups)):
        for j in range(i + 1, len(groups)):
            g1, g2 = groups[i], groups[j]
            v1 = subj.loc[subj["PeopleGroup4"] == g1, dv].dropna().to_numpy(dtype=float)
            v2 = subj.loc[subj["PeopleGroup4"] == g2, dv].dropna().to_numpy(dtype=float)

            if len(v1) < 3 or len(v2) < 3:
                t, p = np.nan, np.nan
            else:
                r = ttest_ind(v1, v2, equal_var=False, nan_policy="omit")
                t, p = float(r.statistic), float(r.pvalue)

            pvals.append(p)
            rows.append({
                "GroupA": g1,
                "GroupB": g2,
                "nA_subjects": len(v1),
                "nB_subjects": len(v2),
                "meanA": float(np.mean(v1)) if len(v1) else np.nan,
                "meanB": float(np.mean(v2)) if len(v2) else np.nan,
                "delta_A_minus_B": (float(np.mean(v1)) - float(np.mean(v2))) if len(v1) and len(v2) else np.nan,
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
        rows[i]["sig_holm"] = sigstar(p_adj[i])

    out = pd.DataFrame(rows)
    if not out.empty:
        out = out.sort_values("p_holm", na_position="last").reset_index(drop=True)
    return out
