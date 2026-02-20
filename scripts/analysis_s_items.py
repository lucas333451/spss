#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import argparse
import json
import warnings

import numpy as np
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
from scipy.stats import ttest_ind
from statsmodels.formula.api import mixedlm
from statsmodels.stats.multitest import multipletests

from analysis_groups import split_tables_by_people_group, compare_people_groups_subject_mean, make_people_group4

warnings.filterwarnings("ignore")

DVS = ["S1", "S2", "S3", "S4", "S5"]


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


def _humanize_term(term: str) -> str:
    t = str(term)
    t = t.replace('C(WWR)[T.', 'WWR: ')
    t = t.replace('C(Complexity)[T.', 'Complexity: ')
    t = t.replace('C(SportFreqGroup)[T.', 'Sport frequency group: ')
    t = t.replace('C(ExperienceGroup)[T.', 'Experience group: ')
    t = t.replace('C(Repetition)[T.', 'Repetition: Round')
    t = t.replace('C(Position)[T.', 'Position: ')
    t = t.replace(']', ' (vs ref)')
    t = t.replace(':', ' × ')
    t = t.replace('Complexity: 1 (vs ref)', 'Complexity: C1/high (vs C0/low)')
    return t


def _coef_table(fit) -> pd.DataFrame:
    ci = fit.conf_int()
    rows = []
    for term in fit.params.index:
        if term.startswith("Group Var") or " Var" in term or " Cov" in term:
            continue
        rows.append({
            "Term": term,
            "APA_Term": _humanize_term(term),
            "Coef": fit.params[term],
            "SE": fit.bse[term],
            "z": fit.tvalues[term],
            "p": fit.pvalues[term],
            "Sig": _sigstar(fit.pvalues[term]),
            "CI95_low": ci.loc[term, 0] if term in ci.index else np.nan,
            "CI95_high": ci.loc[term, 1] if term in ci.index else np.nan,
        })
    return pd.DataFrame(rows)


def _fit_with_fallback(data: pd.DataFrame, formula: str):
    attempts = [
        {"method": "lbfgs", "re_formula": "1 + C(Complexity)"},
        {"method": "powell", "re_formula": "1 + C(Complexity)"},
        {"method": "lbfgs", "re_formula": None},
        {"method": "powell", "re_formula": None},
    ]
    last_err = None
    for a in attempts:
        try:
            fit = mixedlm(
                formula=formula,
                data=data,
                groups=data["SubjectID"],
                re_formula=a["re_formula"],
            ).fit(reml=False, method=a["method"], maxiter=2000)
            return fit, {
                "fit_method": a["method"],
                "re_formula_used": a["re_formula"] if a["re_formula"] else "1",
                "fallback_to_random_intercept": a["re_formula"] is None,
                "converged": bool(getattr(fit, "converged", True)),
                "aic": float(fit.aic) if pd.notna(fit.aic) else np.nan,
                "bic": float(fit.bic) if pd.notna(fit.bic) else np.nan,
                "llf": float(fit.llf) if pd.notna(fit.llf) else np.nan,
            }
        except Exception as e:
            last_err = str(e)
    raise RuntimeError(f"MixedLM failed. formula={formula}, last_error={last_err}")


def subject_consistency(df: pd.DataFrame, dv: str) -> pd.DataFrame:
    rows = []
    for sid, g in df.groupby("SubjectID"):
        piv = g.pivot_table(index="SceneID", columns="Repetition", values=dv, aggfunc="mean")
        if 1 not in piv.columns or 2 not in piv.columns:
            continue
        a, b = piv[1], piv[2]
        valid = a.notna() & b.notna()
        if valid.sum() >= 3:
            corr = a[valid].corr(b[valid])
            delta = (b[valid] - a[valid]).mean()
            sd1 = a[valid].std(ddof=1)
            sd2 = b[valid].std(ddof=1)
        else:
            corr, delta, sd1, sd2 = np.nan, np.nan, np.nan, np.nan
        rows.append({
            "SubjectID": sid,
            "dv": dv,
            "corr_r1_r2": corr,
            "mean_delta_r2_minus_r1": delta,
            "sd_r1": sd1,
            "sd_r2": sd2,
            "sd_change": sd2 - sd1,
        })
    return pd.DataFrame(rows)


def _icc_a1_from_pivot(piv: pd.DataFrame) -> tuple[float, int, int]:
    """ICC(A,1) from a complete targets×raters matrix.

    Returns: (icc_a1, n_targets, n_raters)
    """
    if piv.empty:
        return np.nan, 0, 0

    x = piv.dropna(axis=0, how="any").to_numpy(dtype=float)
    n, k = x.shape
    if n < 2 or k < 2:
        return np.nan, int(n), int(k)

    grand = np.mean(x)
    row_means = np.mean(x, axis=1)
    col_means = np.mean(x, axis=0)

    ssr = k * np.sum((row_means - grand) ** 2)  # targets
    ssc = n * np.sum((col_means - grand) ** 2)  # raters
    sse = np.sum((x - row_means[:, None] - col_means[None, :] + grand) ** 2)

    dfr = n - 1
    dfc = k - 1
    dfe = (n - 1) * (k - 1)

    if dfr <= 0 or dfc <= 0 or dfe <= 0:
        return np.nan, int(n), int(k)

    msr = ssr / dfr
    msc = ssc / dfc
    mse = sse / dfe

    denom = msr + (k - 1) * mse + (k * (msc - mse) / n)
    if denom == 0:
        return np.nan, int(n), int(k)

    icc_a1 = (msr - mse) / denom
    return float(icc_a1), int(n), int(k)


def round_icc_by_group(df: pd.DataFrame, dvs: list[str]) -> pd.DataFrame:
    """Compute ICC(A,1) for Round1/Round2 agreement by PeopleGroup4 and DV.

    Targets are SubjectID×SceneID pairs, raters are Repetition rounds.
    """
    rows = []
    if "PeopleGroup4" not in df.columns:
        df = make_people_group4(df)

    for dv in dvs:
        if dv not in df.columns:
            continue
        sub = df.dropna(subset=["SubjectID", "SceneID", "Repetition", "PeopleGroup4", dv]).copy()
        if sub.empty:
            continue

        for grp, g in sub.groupby("PeopleGroup4", dropna=False):
            piv = g.pivot_table(index=["SubjectID", "SceneID"], columns="Repetition", values=dv, aggfunc="mean")
            # Keep typical two-round setup when available; else use all present rounds
            if 1 in piv.columns and 2 in piv.columns:
                piv2 = piv[[1, 2]].copy()
            else:
                piv2 = piv.copy()

            icc, n_targets, n_raters = _icc_a1_from_pivot(piv2)
            rows.append({
                "DV": dv,
                "PeopleGroup4": grp,
                "n_targets_subject_scene": n_targets,
                "n_raters_rounds": n_raters,
                "icc_a1_round_agreement": icc,
            })

    out = pd.DataFrame(rows)
    if not out.empty:
        out = out.sort_values(["DV", "PeopleGroup4"]).reset_index(drop=True)
    return out


def complexity_group_tables(df: pd.DataFrame, dvs: list[str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Build intuitive group×complexity mean table and pairwise tests on complexity deltas.

    - mean table: per DV × PeopleGroup4, means at C0/C1 and delta (C1-C0)
    - significance table: pairwise tests of subject-level delta across PeopleGroup4
    """
    x = make_people_group4(df)

    mean_rows = []
    sig_rows = []

    for dv in dvs:
        if dv not in x.columns:
            continue

        sub = x.dropna(subset=["SubjectID", "PeopleGroup4", "Complexity", dv]).copy()
        if sub.empty:
            continue

        # subject-level means in each complexity, then group-level summary
        subj = (
            sub.groupby(["SubjectID", "PeopleGroup4", "ExperienceGroup", "SportFreqGroup", "Complexity"], as_index=False)[dv]
            .mean()
        )

        grp = (
            subj.groupby(["PeopleGroup4", "ExperienceGroup", "SportFreqGroup", "Complexity"], as_index=False)
            .agg(
                n_subjects=(dv, "count"),
                mean=(dv, "mean"),
                sd=(dv, "std"),
            )
        )

        piv_mean = grp.pivot_table(index=["PeopleGroup4", "ExperienceGroup", "SportFreqGroup"], columns="Complexity", values="mean", aggfunc="first")
        piv_n = grp.pivot_table(index=["PeopleGroup4", "ExperienceGroup", "SportFreqGroup"], columns="Complexity", values="n_subjects", aggfunc="first")

        c0_col = 0 if 0 in piv_mean.columns else (0.0 if 0.0 in piv_mean.columns else None)
        c1_col = 1 if 1 in piv_mean.columns else (1.0 if 1.0 in piv_mean.columns else None)

        tmp = piv_mean.reset_index().copy()
        tmp.insert(0, "DV", dv)
        tmp["mean_C0"] = tmp[c0_col] if c0_col is not None else np.nan
        tmp["mean_C1"] = tmp[c1_col] if c1_col is not None else np.nan
        tmp["delta_C1_minus_C0"] = tmp["mean_C1"] - tmp["mean_C0"]

        n0 = piv_n[c0_col].reset_index(drop=True) if (c0_col is not None and c0_col in piv_n.columns) else pd.Series([np.nan] * len(tmp))
        n1 = piv_n[c1_col].reset_index(drop=True) if (c1_col is not None and c1_col in piv_n.columns) else pd.Series([np.nan] * len(tmp))
        tmp["n_subj_C0"] = n0.values
        tmp["n_subj_C1"] = n1.values

        keep = ["DV", "PeopleGroup4", "ExperienceGroup", "SportFreqGroup", "n_subj_C0", "n_subj_C1", "mean_C0", "mean_C1", "delta_C1_minus_C0"]
        mean_rows.append(tmp[keep])

        # significance: compare subject-level delta (C1-C0) between groups
        piv_subj = subj.pivot_table(index=["SubjectID", "PeopleGroup4", "ExperienceGroup", "SportFreqGroup"], columns="Complexity", values=dv, aggfunc="mean").reset_index()
        if c0_col in piv_subj.columns and c1_col in piv_subj.columns:
            piv_subj["delta_C1_minus_C0"] = piv_subj[c1_col] - piv_subj[c0_col]
            groups = sorted(piv_subj["PeopleGroup4"].dropna().unique())

            pvals, raw = [], []
            for i in range(len(groups)):
                for j in range(i + 1, len(groups)):
                    g1, g2 = groups[i], groups[j]
                    v1 = piv_subj.loc[piv_subj["PeopleGroup4"] == g1, "delta_C1_minus_C0"].dropna().to_numpy(dtype=float)
                    v2 = piv_subj.loc[piv_subj["PeopleGroup4"] == g2, "delta_C1_minus_C0"].dropna().to_numpy(dtype=float)
                    if len(v1) < 3 or len(v2) < 3:
                        t, p = np.nan, np.nan
                    else:
                        r = ttest_ind(v1, v2, equal_var=False, nan_policy="omit")
                        t, p = float(r.statistic), float(r.pvalue)
                    pvals.append(p)
                    raw.append((g1, g2, len(v1), len(v2), np.mean(v1) if len(v1) else np.nan, np.mean(v2) if len(v2) else np.nan, t, p))

            valid = np.isfinite(pvals)
            p_adj = [np.nan] * len(pvals)
            if np.any(valid):
                _, corr, _, _ = multipletests(np.array(pvals)[valid], method="holm")
                k = 0
                for idx, ok in enumerate(valid):
                    if ok:
                        p_adj[idx] = float(corr[k])
                        k += 1

            for (g1, g2, n1s, n2s, m1, m2, t, p), ph in zip(raw, p_adj):
                sig_rows.append({
                    "DV": dv,
                    "GroupA": g1,
                    "GroupB": g2,
                    "nA_subjects": n1s,
                    "nB_subjects": n2s,
                    "meanDeltaA_C1_minus_C0": m1,
                    "meanDeltaB_C1_minus_C0": m2,
                    "delta_of_delta_A_minus_B": (m1 - m2) if pd.notna(m1) and pd.notna(m2) else np.nan,
                    "t_welch": t,
                    "p": p,
                    "p_holm": ph,
                    "sig_holm": _sigstar(ph),
                })

    mean_df = pd.concat(mean_rows, ignore_index=True) if mean_rows else pd.DataFrame()
    sig_df = pd.DataFrame(sig_rows)
    if not sig_df.empty:
        sig_df = sig_df.sort_values(["DV", "p_holm"], na_position="last").reset_index(drop=True)
    return mean_df, sig_df


def complexity_group_tables_by_wwr(df: pd.DataFrame, dvs: list[str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """WWR-stratified version of complexity deltas (C1-C0) by people group."""
    x = make_people_group4(df)
    mean_rows = []
    sig_rows = []

    for dv in dvs:
        if dv not in x.columns:
            continue

        sub = x.dropna(subset=["SubjectID", "PeopleGroup4", "Complexity", "WWR", dv]).copy()
        if sub.empty:
            continue

        subj = (
            sub.groupby(["SubjectID", "PeopleGroup4", "ExperienceGroup", "SportFreqGroup", "WWR", "Complexity"], as_index=False)[dv]
            .mean()
        )

        grp = (
            subj.groupby(["PeopleGroup4", "ExperienceGroup", "SportFreqGroup", "WWR", "Complexity"], as_index=False)
            .agg(
                n_subjects=(dv, "count"),
                mean=(dv, "mean"),
                sd=(dv, "std"),
            )
        )

        for wwr, gwwr in grp.groupby("WWR", dropna=False):
            piv_mean = gwwr.pivot_table(index=["PeopleGroup4", "ExperienceGroup", "SportFreqGroup"], columns="Complexity", values="mean", aggfunc="first")
            piv_n = gwwr.pivot_table(index=["PeopleGroup4", "ExperienceGroup", "SportFreqGroup"], columns="Complexity", values="n_subjects", aggfunc="first")

            c0_col = 0 if 0 in piv_mean.columns else (0.0 if 0.0 in piv_mean.columns else None)
            c1_col = 1 if 1 in piv_mean.columns else (1.0 if 1.0 in piv_mean.columns else None)

            tmp = piv_mean.reset_index().copy()
            tmp.insert(0, "DV", dv)
            tmp.insert(1, "WWR", wwr)
            tmp["mean_C0"] = tmp[c0_col] if c0_col is not None else np.nan
            tmp["mean_C1"] = tmp[c1_col] if c1_col is not None else np.nan
            tmp["delta_C1_minus_C0"] = tmp["mean_C1"] - tmp["mean_C0"]

            n0 = piv_n[c0_col].reset_index(drop=True) if (c0_col is not None and c0_col in piv_n.columns) else pd.Series([np.nan] * len(tmp))
            n1 = piv_n[c1_col].reset_index(drop=True) if (c1_col is not None and c1_col in piv_n.columns) else pd.Series([np.nan] * len(tmp))
            tmp["n_subj_C0"] = n0.values
            tmp["n_subj_C1"] = n1.values
            mean_rows.append(tmp[["DV", "WWR", "PeopleGroup4", "ExperienceGroup", "SportFreqGroup", "n_subj_C0", "n_subj_C1", "mean_C0", "mean_C1", "delta_C1_minus_C0"]])

        # significance by WWR: compare subject-level deltas across groups
        for wwr, gwwr in subj.groupby("WWR", dropna=False):
            piv_subj = gwwr.pivot_table(index=["SubjectID", "PeopleGroup4"], columns="Complexity", values=dv, aggfunc="mean").reset_index()
            c0_col = 0 if 0 in piv_subj.columns else (0.0 if 0.0 in piv_subj.columns else None)
            c1_col = 1 if 1 in piv_subj.columns else (1.0 if 1.0 in piv_subj.columns else None)
            if c0_col is None or c1_col is None:
                continue
            piv_subj["delta_C1_minus_C0"] = piv_subj[c1_col] - piv_subj[c0_col]
            groups = sorted(piv_subj["PeopleGroup4"].dropna().unique())

            pvals, raw = [], []
            for i in range(len(groups)):
                for j in range(i + 1, len(groups)):
                    g1, g2 = groups[i], groups[j]
                    v1 = piv_subj.loc[piv_subj["PeopleGroup4"] == g1, "delta_C1_minus_C0"].dropna().to_numpy(dtype=float)
                    v2 = piv_subj.loc[piv_subj["PeopleGroup4"] == g2, "delta_C1_minus_C0"].dropna().to_numpy(dtype=float)
                    if len(v1) < 3 or len(v2) < 3:
                        t, p = np.nan, np.nan
                    else:
                        r = ttest_ind(v1, v2, equal_var=False, nan_policy="omit")
                        t, p = float(r.statistic), float(r.pvalue)
                    pvals.append(p)
                    raw.append((g1, g2, len(v1), len(v2), np.mean(v1) if len(v1) else np.nan, np.mean(v2) if len(v2) else np.nan, t, p))

            valid = np.isfinite(pvals)
            p_adj = [np.nan] * len(pvals)
            if np.any(valid):
                _, corr, _, _ = multipletests(np.array(pvals)[valid], method="holm")
                k = 0
                for idx, ok in enumerate(valid):
                    if ok:
                        p_adj[idx] = float(corr[k])
                        k += 1

            for (g1, g2, n1s, n2s, m1, m2, t, p), ph in zip(raw, p_adj):
                sig_rows.append({
                    "DV": dv,
                    "WWR": wwr,
                    "GroupA": g1,
                    "GroupB": g2,
                    "nA_subjects": n1s,
                    "nB_subjects": n2s,
                    "meanDeltaA_C1_minus_C0": m1,
                    "meanDeltaB_C1_minus_C0": m2,
                    "delta_of_delta_A_minus_B": (m1 - m2) if pd.notna(m1) and pd.notna(m2) else np.nan,
                    "t_welch": t,
                    "p": p,
                    "p_holm": ph,
                    "sig_holm": _sigstar(ph),
                })

    mean_df = pd.concat(mean_rows, ignore_index=True) if mean_rows else pd.DataFrame()
    sig_df = pd.DataFrame(sig_rows)
    if not sig_df.empty:
        sig_df = sig_df.sort_values(["DV", "WWR", "p_holm"], na_position="last").reset_index(drop=True)
    return mean_df, sig_df


def complexity_delta_by_round(df: pd.DataFrame, dvs: list[str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Detailed C1-C0 deltas split by Repetition (round/order), with round contrast."""
    x = make_people_group4(df)
    rows = []
    rounddiff_rows = []

    for dv in dvs:
        if dv not in x.columns:
            continue

        sub = x.dropna(subset=["SubjectID", "PeopleGroup4", "Complexity", "WWR", "Repetition", dv]).copy()
        if sub.empty:
            continue

        subj = (
            sub.groupby(["SubjectID", "PeopleGroup4", "ExperienceGroup", "SportFreqGroup", "WWR", "Repetition", "Complexity"], as_index=False)[dv]
            .mean()
        )
        piv = subj.pivot_table(
            index=["SubjectID", "PeopleGroup4", "ExperienceGroup", "SportFreqGroup", "WWR", "Repetition"],
            columns="Complexity",
            values=dv,
            aggfunc="mean",
        ).reset_index()

        c0_col = 0 if 0 in piv.columns else (0.0 if 0.0 in piv.columns else None)
        c1_col = 1 if 1 in piv.columns else (1.0 if 1.0 in piv.columns else None)
        if c0_col is None or c1_col is None:
            continue
        piv["delta_C1_minus_C0"] = piv[c1_col] - piv[c0_col]

        grp = (
            piv.groupby(["PeopleGroup4", "ExperienceGroup", "SportFreqGroup", "WWR", "Repetition"], as_index=False)["delta_C1_minus_C0"]
            .agg(n_subjects="count", mean_delta="mean", sd_delta="std")
        )
        grp.insert(0, "DV", dv)
        rows.append(grp)

        piv_round = piv.pivot_table(
            index=["SubjectID", "PeopleGroup4", "ExperienceGroup", "SportFreqGroup", "WWR"],
            columns="Repetition",
            values="delta_C1_minus_C0",
            aggfunc="mean",
        ).reset_index()
        if 1 in piv_round.columns and 2 in piv_round.columns:
            piv_round["delta_round2_minus_round1"] = piv_round[2] - piv_round[1]
            rd = (
                piv_round.groupby(["PeopleGroup4", "ExperienceGroup", "SportFreqGroup", "WWR"], as_index=False)["delta_round2_minus_round1"]
                .agg(n_subjects="count", mean="mean", sd="std")
            )
            rd.insert(0, "DV", dv)
            rounddiff_rows.append(rd)

    detail_df = pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()
    rounddiff_df = pd.concat(rounddiff_rows, ignore_index=True) if rounddiff_rows else pd.DataFrame()
    return detail_df, rounddiff_df


def make_people_group2(df: pd.DataFrame, source: str = "SportFreqGroup") -> pd.DataFrame:
    x = df.copy()
    if source not in x.columns:
        x["PeopleGroup2"] = "Unknown"
    else:
        x["PeopleGroup2"] = x[source].astype(str)
    return x


def split_tables_by_people_group2(df: pd.DataFrame, out_dir: Path, source: str = "SportFreqGroup") -> pd.DataFrame:
    out_dir.mkdir(parents=True, exist_ok=True)
    x = make_people_group2(df, source=source)
    src = str(source).replace("/", "_").replace(" ", "").lower()
    rows = []
    for grp, g in x.groupby("PeopleGroup2", dropna=False):
        safe = str(grp).replace("/", "_").replace(" ", "")
        f = out_dir / f"group2_{src}_{safe}.csv"
        g.to_csv(f, index=False, encoding="utf-8-sig")
        rows.append({
            "PeopleGroup2": grp,
            "source": source,
            "n_rows": int(len(g)),
            "n_subjects": int(g["SubjectID"].nunique()),
            "file": str(f),
        })
    m = pd.DataFrame(rows)
    m.to_csv(out_dir / f"manifest_group2_{src}.csv", index=False, encoding="utf-8-sig")
    return m


def compare_people_group2_subject_mean(df: pd.DataFrame, dvs: list[str], source: str = "SportFreqGroup") -> pd.DataFrame:
    x = make_people_group2(df, source=source)
    groups = sorted(x["PeopleGroup2"].dropna().unique())
    if len(groups) < 2:
        return pd.DataFrame()

    rows = []
    for dv in dvs:
        if dv not in x.columns:
            continue
        subj = x.dropna(subset=[dv, "SubjectID", "PeopleGroup2"]).groupby(["SubjectID", "PeopleGroup2"], as_index=False)[dv].mean()

        # for binary split, compare first two groups
        g1, g2 = groups[0], groups[1]
        v1 = subj.loc[subj["PeopleGroup2"] == g1, dv].dropna().to_numpy(dtype=float)
        v2 = subj.loc[subj["PeopleGroup2"] == g2, dv].dropna().to_numpy(dtype=float)
        if len(v1) < 3 or len(v2) < 3:
            t, p = np.nan, np.nan
        else:
            r = ttest_ind(v1, v2, equal_var=False, nan_policy="omit")
            t, p = float(r.statistic), float(r.pvalue)
        rows.append({
            "DV": dv,
            "source": source,
            "GroupA": g1,
            "GroupB": g2,
            "nA_subjects": len(v1),
            "nB_subjects": len(v2),
            "meanA": float(np.mean(v1)) if len(v1) else np.nan,
            "meanB": float(np.mean(v2)) if len(v2) else np.nan,
            "delta_A_minus_B": (float(np.mean(v1)) - float(np.mean(v2))) if len(v1) and len(v2) else np.nan,
            "t_welch": t,
            "p": p,
            "sig": _sigstar(p),
        })
    return pd.DataFrame(rows)


def group2_complexity_table(df: pd.DataFrame, dvs: list[str], source: str = "SportFreqGroup") -> tuple[pd.DataFrame, pd.DataFrame]:
    x = make_people_group2(df, source=source)
    mean_rows, sig_rows = [], []
    for dv in dvs:
        if dv not in x.columns:
            continue
        sub = x.dropna(subset=["SubjectID", "PeopleGroup2", "Complexity", dv]).copy()
        if sub.empty:
            continue

        subj = sub.groupby(["SubjectID", "PeopleGroup2", "Complexity"], as_index=False)[dv].mean()
        grp = subj.groupby(["PeopleGroup2", "Complexity"], as_index=False).agg(n_subjects=(dv, "count"), mean=(dv, "mean"), sd=(dv, "std"))
        piv = grp.pivot_table(index="PeopleGroup2", columns="Complexity", values="mean", aggfunc="first").reset_index()
        c0 = 0 if 0 in piv.columns else (0.0 if 0.0 in piv.columns else None)
        c1 = 1 if 1 in piv.columns else (1.0 if 1.0 in piv.columns else None)
        piv.insert(0, "DV", dv)
        piv["mean_C0"] = piv[c0] if c0 is not None else np.nan
        piv["mean_C1"] = piv[c1] if c1 is not None else np.nan
        piv["delta_C1_minus_C0"] = piv["mean_C1"] - piv["mean_C0"]
        mean_rows.append(piv[["DV", "PeopleGroup2", "mean_C0", "mean_C1", "delta_C1_minus_C0"]])

        # delta significance between two groups
        piv_subj = subj.pivot_table(index=["SubjectID", "PeopleGroup2"], columns="Complexity", values=dv, aggfunc="mean").reset_index()
        if c0 in piv_subj.columns and c1 in piv_subj.columns:
            piv_subj["delta"] = piv_subj[c1] - piv_subj[c0]
            gs = sorted(piv_subj["PeopleGroup2"].dropna().unique())
            if len(gs) >= 2:
                g1, g2 = gs[0], gs[1]
                v1 = piv_subj.loc[piv_subj["PeopleGroup2"] == g1, "delta"].dropna().to_numpy(dtype=float)
                v2 = piv_subj.loc[piv_subj["PeopleGroup2"] == g2, "delta"].dropna().to_numpy(dtype=float)
                if len(v1) < 3 or len(v2) < 3:
                    t, p = np.nan, np.nan
                else:
                    rr = ttest_ind(v1, v2, equal_var=False, nan_policy="omit")
                    t, p = float(rr.statistic), float(rr.pvalue)
                sig_rows.append({
                    "DV": dv,
                    "source": source,
                    "GroupA": g1,
                    "GroupB": g2,
                    "meanDeltaA_C1_minus_C0": float(np.mean(v1)) if len(v1) else np.nan,
                    "meanDeltaB_C1_minus_C0": float(np.mean(v2)) if len(v2) else np.nan,
                    "delta_of_delta_A_minus_B": (float(np.mean(v1)) - float(np.mean(v2))) if len(v1) and len(v2) else np.nan,
                    "t_welch": t,
                    "p": p,
                    "sig": _sigstar(p),
                })

    return (pd.concat(mean_rows, ignore_index=True) if mean_rows else pd.DataFrame(), pd.DataFrame(sig_rows))


def group_item_variance(df: pd.DataFrame, dvs: list[str]) -> pd.DataFrame:
    rows = []
    x = make_people_group4(df)
    for dv in dvs:
        if dv not in x.columns:
            continue
        sub = x.dropna(subset=[dv, "PeopleGroup4", "SubjectID"])
        if sub.empty:
            continue
        global_sd = float(sub[dv].std(ddof=1)) if sub[dv].notna().sum() >= 2 else np.nan
        for grp4, g in sub.groupby("PeopleGroup4", dropna=False):
            vals = g[dv].dropna().to_numpy(dtype=float)
            sd = float(np.std(vals, ddof=1)) if len(vals) >= 2 else np.nan
            iqr = float(np.percentile(vals, 75) - np.percentile(vals, 25)) if len(vals) >= 2 else np.nan
            mean = float(np.mean(vals)) if len(vals) else np.nan
            cv = float(sd / mean) if (pd.notna(sd) and pd.notna(mean) and mean != 0) else np.nan
            high_abs = bool(pd.notna(sd) and sd >= 1.5)
            high_rel = bool(pd.notna(sd) and pd.notna(global_sd) and sd >= 1.25 * global_sd)
            rows.append({
                "DV": dv,
                "PeopleGroup4": grp4,
                "ExperienceGroup": g["ExperienceGroup"].iloc[0],
                "SportFreqGroup": g["SportFreqGroup"].iloc[0],
                "n_rows": int(len(vals)),
                "n_subjects": int(g["SubjectID"].nunique()),
                "mean": mean,
                "sd": sd,
                "iqr": iqr,
                "cv": cv,
                "global_sd_dv": global_sd,
                "high_variance_flag": bool(high_abs or high_rel),
            })
    out = pd.DataFrame(rows)
    return out.sort_values(["DV", "high_variance_flag", "sd"], ascending=[True, False, False]).reset_index(drop=True) if not out.empty else out


def main():
    ap = argparse.ArgumentParser(description="S-item analysis (Angle1/Angle2) with 4-group + 2-group splits")
    ap.add_argument("--long-csv", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, default=Path("results/research"))
    args = ap.parse_args()

    out = args.out_dir
    out.mkdir(parents=True, exist_ok=True)
    (out / "figures").mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(args.long_csv)
    required = ["SubjectID", "WWR", "Complexity", "Position", "S1", "S2", "S3", "S4", "S5"]
    for c in required:
        if c not in df.columns:
            raise SystemExit(f"Missing required column: {c}")

    if "ExperienceGroup" not in df.columns:
        df["ExperienceGroup"] = "Unknown"
    if "SportFreqGroup" not in df.columns:
        df["SportFreqGroup"] = "Unknown"
    if "Repetition" not in df.columns:
        df["Repetition"] = df["Block"] if "Block" in df.columns else np.nan

    df["WWR"] = pd.to_numeric(df["WWR"], errors="coerce")
    df["Complexity"] = pd.to_numeric(df["Complexity"], errors="coerce")
    df["Position"] = pd.to_numeric(df["Position"], errors="coerce")
    df["Repetition"] = pd.to_numeric(df["Repetition"], errors="coerce")
    df = make_people_group4(df)

    angle1_all, angle2_all, model_log, consistency_all = [], [], [], []

    for dv in DVS:
        sub = df.dropna(subset=["SubjectID", dv, "WWR", "Complexity", "Position", "ExperienceGroup", "SportFreqGroup", "Repetition"]).copy()
        if sub.empty:
            continue

        for c in ["WWR", "Complexity", "Position", "ExperienceGroup", "SportFreqGroup", "Repetition"]:
            sub[c] = sub[c].astype(str)

        formula_a1 = f"{dv} ~ C(WWR) * C(Complexity) * C(SportFreqGroup) + C(ExperienceGroup) + C(Repetition) + C(Position)"
        fit_a1, info_a1 = _fit_with_fallback(sub, formula_a1)
        coef_a1 = _coef_table(fit_a1)
        coef_a1.insert(0, "DV", dv)
        coef_a1.insert(1, "Angle", "Angle1_main_interaction")
        coef_a1.insert(2, "Formula", formula_a1)
        angle1_all.append(coef_a1)
        model_log.append({"DV": dv, "Angle": "Angle1_main_interaction", "formula": formula_a1, **info_a1, "n_rows": int(len(sub)), "n_subjects": int(sub["SubjectID"].nunique())})

        formula_a2 = f"{dv} ~ C(Repetition) * C(WWR) * C(Complexity) * C(SportFreqGroup) + C(ExperienceGroup) + C(Position)"
        fit_a2, info_a2 = _fit_with_fallback(sub, formula_a2)
        coef_a2 = _coef_table(fit_a2)
        coef_a2.insert(0, "DV", dv)
        coef_a2.insert(1, "Angle", "Angle2_round_convergence")
        coef_a2.insert(2, "Formula", formula_a2)
        angle2_all.append(coef_a2)
        model_log.append({"DV": dv, "Angle": "Angle2_round_convergence", "formula": formula_a2, **info_a2, "n_rows": int(len(sub)), "n_subjects": int(sub["SubjectID"].nunique())})

        csub = df.dropna(subset=["SubjectID", dv, "SceneID", "Repetition", "SportFreqGroup"]).copy()
        cdf = subject_consistency(csub, dv)
        cdf = cdf.merge(csub[["SubjectID", "SportFreqGroup", "ExperienceGroup"]].drop_duplicates(), on="SubjectID", how="left")
        cdf = make_people_group4(cdf)
        consistency_all.append(cdf)

    if not angle1_all and not angle2_all:
        raise SystemExit("No analyzable DV found.")

    angle1_df = pd.concat(angle1_all, ignore_index=True) if angle1_all else pd.DataFrame()
    angle2_df = pd.concat(angle2_all, ignore_index=True) if angle2_all else pd.DataFrame()
    all_coef_df = pd.concat([x for x in [angle1_df, angle2_df] if not x.empty], ignore_index=True)
    all_coef_df.to_csv(out / "table_fixed_effects_all_dv.csv", index=False, encoding="utf-8-sig")

    if not angle1_df.empty:
        angle1_df.to_csv(out / "table_angle1_effects_all_dv.csv", index=False, encoding="utf-8-sig")
        angle1_df[angle1_df["Term"].str.contains("C\\(WWR\\)|C\\(Complexity\\)|C\\(SportFreqGroup\\)", regex=True, na=False)].to_csv(out / "table_angle1_main_interactions_all_dv.csv", index=False, encoding="utf-8-sig")

    if not angle2_df.empty:
        angle2_df.to_csv(out / "table_angle2_effects_all_dv.csv", index=False, encoding="utf-8-sig")
        angle2_df[angle2_df["Term"].str.contains("C\\(Repetition\\)|C\\(WWR\\)|C\\(Complexity\\)|C\\(SportFreqGroup\\)", regex=True, na=False)].to_csv(out / "table_angle2_round_interactions_all_dv.csv", index=False, encoding="utf-8-sig")

    all_coef_df[all_coef_df["Term"].str.contains("C\\(WWR\\)|C\\(Complexity\\)|C\\(SportFreqGroup\\)|C\\(ExperienceGroup\\)|C\\(Repetition\\)", regex=True, na=False)].to_csv(out / "table_main_interactions_all_dv.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(model_log).to_csv(out / "model_log.csv", index=False, encoding="utf-8-sig")

    cons_df = pd.concat(consistency_all, ignore_index=True) if consistency_all else pd.DataFrame()
    cons_df.to_csv(out / "round_consistency_by_subject.csv", index=False, encoding="utf-8-sig")
    if not cons_df.empty:
        cons_grp = cons_df.groupby(["dv", "SportFreqGroup", "ExperienceGroup", "PeopleGroup4"], dropna=False).agg(
            n=("SubjectID", "nunique"),
            corr_mean=("corr_r1_r2", "mean"),
            corr_sd=("corr_r1_r2", "std"),
            sd_change_mean=("sd_change", "mean"),
            delta_mean=("mean_delta_r2_minus_r1", "mean"),
        ).reset_index()
    else:
        cons_grp = pd.DataFrame()
    cons_grp.to_csv(out / "round_consistency_by_group.csv", index=False, encoding="utf-8-sig")

    # ICC(A,1): round agreement by group and DV
    icc_df = round_icc_by_group(df, DVS)
    icc_df.to_csv(out / "round_icc_by_group.csv", index=False, encoding="utf-8-sig")

    groups_manifest = split_tables_by_people_group(df, out / "groups")

    # 2-group split: export BOTH dimensions separately (SportFreqGroup and ExperienceGroup)
    group2_sources = ["SportFreqGroup", "ExperienceGroup"]
    group2_manifest_all, group2_cmp_all, group2_mean_all, group2_sig_all = [], [], [], []

    for gsrc in group2_sources:
        g2m = split_tables_by_people_group2(df, out / "groups", source=gsrc)
        g2c = compare_people_group2_subject_mean(df, DVS, source=gsrc)
        g2mean, g2sig = group2_complexity_table(df, DVS, source=gsrc)

        if not g2m.empty:
            group2_manifest_all.append(g2m)
        if not g2c.empty:
            group2_cmp_all.append(g2c)
        if not g2mean.empty:
            group2_mean_all.append(g2mean.assign(source=gsrc))
        if not g2sig.empty:
            group2_sig_all.append(g2sig)

        # per-source files
        src_tag = gsrc.lower()
        g2c.to_csv(out / f"group2_comparisons_item_level_{src_tag}.csv", index=False, encoding="utf-8-sig")
        g2mean.to_csv(out / f"group2_complexity_mean_table_{src_tag}.csv", index=False, encoding="utf-8-sig")
        g2sig.to_csv(out / f"group2_complexity_delta_significance_{src_tag}.csv", index=False, encoding="utf-8-sig")

    # merged files (both two-way splits together)
    groups2_manifest = pd.concat(group2_manifest_all, ignore_index=True) if group2_manifest_all else pd.DataFrame()
    group2_cmp = pd.concat(group2_cmp_all, ignore_index=True) if group2_cmp_all else pd.DataFrame()
    group2_mean_df = pd.concat(group2_mean_all, ignore_index=True) if group2_mean_all else pd.DataFrame()
    group2_sig_df = pd.concat(group2_sig_all, ignore_index=True) if group2_sig_all else pd.DataFrame()

    groups2_manifest.to_csv(out / "groups" / "manifest_group2_all.csv", index=False, encoding="utf-8-sig")
    group2_cmp.to_csv(out / "group2_comparisons_item_level.csv", index=False, encoding="utf-8-sig")
    group2_mean_df.to_csv(out / "group2_complexity_mean_table.csv", index=False, encoding="utf-8-sig")
    group2_sig_df.to_csv(out / "group2_complexity_delta_significance.csv", index=False, encoding="utf-8-sig")

    cmp_rows = []
    for dv in DVS:
        if dv in df.columns:
            t = compare_people_groups_subject_mean(df, dv)
            if not t.empty:
                t.insert(0, "DV", dv)
                cmp_rows.append(t)
    group_cmp = pd.concat(cmp_rows, ignore_index=True) if cmp_rows else pd.DataFrame()
    group_cmp.to_csv(out / "group_comparisons_item_level.csv", index=False, encoding="utf-8-sig")

    # intuitive 2D table: PeopleGroup4 × Complexity means (per DV)
    mean_2d_df, sig_2d_df = complexity_group_tables(df, DVS)
    mean_2d_df.to_csv(out / "group_complexity_mean_table.csv", index=False, encoding="utf-8-sig")
    sig_2d_df.to_csv(out / "group_complexity_delta_significance.csv", index=False, encoding="utf-8-sig")

    # WWR-stratified complexity delta tables
    mean_wwr_df, sig_wwr_df = complexity_group_tables_by_wwr(df, DVS)
    mean_wwr_df.to_csv(out / "group_complexity_mean_table_by_wwr.csv", index=False, encoding="utf-8-sig")
    sig_wwr_df.to_csv(out / "group_complexity_delta_significance_by_wwr.csv", index=False, encoding="utf-8-sig")

    # detailed split by round (group1/group2 viewing order)
    delta_round_detail_df, delta_round_shift_df = complexity_delta_by_round(df, DVS)
    delta_round_detail_df.to_csv(out / "group_complexity_delta_by_round.csv", index=False, encoding="utf-8-sig")
    delta_round_shift_df.to_csv(out / "group_complexity_delta_round_shift.csv", index=False, encoding="utf-8-sig")

    # new visualization: PeopleGroup4 × Complexity (per DV)
    if not mean_2d_df.empty:
        for dv in DVS:
            d2 = mean_2d_df[mean_2d_df["DV"] == dv].copy()
            if d2.empty:
                continue

            # heatmap: mean by group and complexity
            hm = d2.set_index("PeopleGroup4")[["mean_C0", "mean_C1"]].copy()
            hm = hm.rename(columns={"mean_C0": "C0", "mean_C1": "C1"})
            plt.figure(figsize=(6, max(3, 0.6 * len(hm))))
            sns.heatmap(hm, annot=True, fmt=".2f", cmap="YlGnBu")
            plt.title(f"{dv}: PeopleGroup4 × Complexity Mean")
            plt.xlabel("Complexity")
            plt.ylabel("PeopleGroup4")
            plt.tight_layout()
            plt.savefig(out / "figures" / f"group_complexity_heatmap_{dv}.png", dpi=220)
            plt.close()

            # bar: delta C1-C0 by group
            b = d2[["PeopleGroup4", "delta_C1_minus_C0"]].copy()
            b = b.sort_values("delta_C1_minus_C0")
            plt.figure(figsize=(7, max(3, 0.5 * len(b))))
            sns.barplot(data=b, x="delta_C1_minus_C0", y="PeopleGroup4", orient="h", color="#4C72B0")
            plt.axvline(0, color="black", linewidth=1)
            plt.title(f"{dv}: Delta (C1 - C0) by PeopleGroup4")
            plt.xlabel("C1 - C0")
            plt.ylabel("PeopleGroup4")
            plt.tight_layout()
            plt.savefig(out / "figures" / f"group_complexity_delta_{dv}.png", dpi=220)
            plt.close()

    var_df = group_item_variance(df, DVS)
    var_df.to_csv(out / "item_variance_by_group.csv", index=False, encoding="utf-8-sig")
    if not var_df.empty:
        var_summary = var_df.groupby(["DV", "PeopleGroup4", "SportFreqGroup", "ExperienceGroup"], dropna=False).agg(
            n_rows=("n_rows", "sum"),
            n_subjects=("n_subjects", "max"),
            mean_sd=("sd", "mean"),
            max_sd=("sd", "max"),
            any_high_variance=("high_variance_flag", "max"),
        ).reset_index()
    else:
        var_summary = pd.DataFrame()
    var_summary.to_csv(out / "item_variance_summary_by_group.csv", index=False, encoding="utf-8-sig")

    for dv in DVS:
        if dv not in df.columns:
            continue
        h = df.dropna(subset=[dv, "WWR", "Complexity", "SportFreqGroup"]).copy()
        for fg, g in h.groupby("SportFreqGroup"):
            piv = g.pivot_table(index="Complexity", columns="WWR", values=dv, aggfunc="mean")
            plt.figure(figsize=(5, 4))
            sns.heatmap(piv, annot=True, fmt=".2f", cmap="YlGnBu")
            plt.title(f"{dv} Mean Heatmap ({fg})")
            plt.tight_layout()
            plt.savefig(out / "figures" / f"heatmap_{dv}_{fg}.png", dpi=220)
            plt.close()

        g = df.dropna(subset=[dv, "WWR", "Complexity", "SportFreqGroup"]).copy()
        g["WWR"] = g["WWR"].astype(int).astype(str)
        g["Complexity"] = g["Complexity"].map({0: "C0", 1: "C1"}).fillna(g["Complexity"].astype(str))
        p = sns.catplot(data=g, x="WWR", y=dv, hue="Complexity", col="SportFreqGroup", kind="point", errorbar="se", dodge=True, height=4, aspect=1)
        p.fig.suptitle(f"WWR × Complexity on {dv} by Sport Frequency Group", y=1.05)
        p.savefig(out / "figures" / f"interaction_{dv}_by_sportfreqgroup.png", dpi=220)
        plt.close("all")

        d = df.dropna(subset=[dv, "SubjectID", "SceneID", "Repetition", "SportFreqGroup"]).copy()
        piv = d.pivot_table(index=["SubjectID", "SceneID", "SportFreqGroup"], columns="Repetition", values=dv, aggfunc="mean").reset_index()
        if 1 in piv.columns and 2 in piv.columns:
            piv["Diff_R2_minus_R1"] = piv[2] - piv[1]
            plt.figure(figsize=(6, 4))
            sns.boxplot(data=piv, x="SportFreqGroup", y="Diff_R2_minus_R1")
            sns.stripplot(data=piv, x="SportFreqGroup", y="Diff_R2_minus_R1", color="black", alpha=0.35, size=3)
            plt.title(f"Round2 - Round1 ({dv}) by Sport Frequency Group")
            plt.tight_layout()
            plt.savefig(out / "figures" / f"round_diff_{dv}_by_sportfreqgroup.png", dpi=220)
            plt.close()

    summary = {
        "dvs": DVS,
        "people_groups": groups_manifest.to_dict(orient="records") if isinstance(groups_manifest, pd.DataFrame) else [],
        "people_groups2": groups2_manifest.to_dict(orient="records") if isinstance(groups2_manifest, pd.DataFrame) else [],
        "outputs": [
            "table_fixed_effects_all_dv.csv",
            "table_angle1_effects_all_dv.csv",
            "table_angle1_main_interactions_all_dv.csv",
            "table_angle2_effects_all_dv.csv",
            "table_angle2_round_interactions_all_dv.csv",
            "table_main_interactions_all_dv.csv",
            "model_log.csv",
            "round_consistency_by_subject.csv",
            "round_consistency_by_group.csv",
            "round_icc_by_group.csv",
            "groups/manifest.csv",
            "groups/group_*.csv",
            "groups/manifest_group2_all.csv",
            "groups/manifest_group2_*.csv",
            "groups/group2_*.csv",
            "group_comparisons_item_level.csv",
            "group2_comparisons_item_level.csv",
            "group2_complexity_mean_table.csv",
            "group2_complexity_delta_significance.csv",
            "group_complexity_mean_table.csv",
            "group_complexity_delta_significance.csv",
            "group_complexity_mean_table_by_wwr.csv",
            "group_complexity_delta_significance_by_wwr.csv",
            "group_complexity_delta_by_round.csv",
            "group_complexity_delta_round_shift.csv",
            "figures/group_complexity_heatmap_S*.png",
            "figures/group_complexity_delta_S*.png",
            "item_variance_by_group.csv",
            "item_variance_summary_by_group.csv",
            "figures/heatmap_S*_*.png",
            "figures/interaction_S*_by_sportfreqgroup.png",
            "figures/round_diff_S*_by_sportfreqgroup.png",
        ]
    }
    (out / "analysis_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
