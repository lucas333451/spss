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
from statsmodels.formula.api import mixedlm

warnings.filterwarnings("ignore")

DVS = ["S1", "S2", "S3", "S4", "S5", "Afford4", "Afford5"]


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
    t = t.replace('Complexity: 0 (vs ref)', 'Complexity: C0/low (vs C1/high)')
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
                "re_formula_used": a["re_formula"],
                "fallback_to_random_intercept": a["re_formula"] is None,
                "converged": bool(getattr(fit, "converged", True)),
            }
        except Exception as e:
            last_err = str(e)
            continue

    raise RuntimeError(f"MixedLM failed. formula={formula}, last_error={last_err}")


def subject_consistency(df: pd.DataFrame, dv: str) -> pd.DataFrame:
    rows = []
    for sid, g in df.groupby("SubjectID"):
        piv = g.pivot_table(index="SceneID", columns="Repetition", values=dv, aggfunc="mean")
        if 1 in piv.columns and 2 in piv.columns:
            a = piv[1]
            b = piv[2]
        else:
            continue
        valid = a.notna() & b.notna()
        if valid.sum() >= 3:
            corr = a[valid].corr(b[valid])
            delta = (b[valid] - a[valid]).mean()
            sd1 = a[valid].std(ddof=1)
            sd2 = b[valid].std(ddof=1)
        else:
            corr, delta, sd1, sd2 = np.nan, np.nan, np.nan, np.nan
        rows.append({"SubjectID": sid, "dv": dv, "corr_r1_r2": corr, "mean_delta_r2_minus_r1": delta, "sd_r1": sd1, "sd_r2": sd2, "sd_change": sd2 - sd1})
    return pd.DataFrame(rows)


def main():
    ap = argparse.ArgumentParser(description="Angle1+Angle2 analysis for WWR×Complexity with Experience/SportFreq/Repetition controls")
    ap.add_argument("--long-csv", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, default=Path("results/research"))
    args = ap.parse_args()

    out = args.out_dir
    out.mkdir(parents=True, exist_ok=True)
    (out / "figures").mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(args.long_csv)

    required_cols = ["SubjectID", "WWR", "Complexity", "Position", "Afford5"]
    for c in required_cols:
        if c not in df.columns:
            raise SystemExit(f"Missing required column: {c}")

    if "ExperienceGroup" not in df.columns:
        df["ExperienceGroup"] = "Unknown"
    if "SportFreqGroup" not in df.columns:
        df["SportFreqGroup"] = "Unknown"
    if "Repetition" not in df.columns:
        df["Repetition"] = df["Block"] if "Block" in df.columns else np.nan

    # numeric harmonization for consistency analysis
    df["WWR"] = pd.to_numeric(df["WWR"], errors="coerce")
    df["Complexity"] = pd.to_numeric(df["Complexity"], errors="coerce")
    df["Position"] = pd.to_numeric(df["Position"], errors="coerce")
    df["Repetition"] = pd.to_numeric(df["Repetition"], errors="coerce")

    all_coefs = []
    model_log = []
    consistency_all = []

    for dv in DVS:
        if dv not in df.columns:
            continue

        sub = df.dropna(subset=["SubjectID", dv, "WWR", "Complexity", "Position", "ExperienceGroup", "SportFreqGroup", "Repetition"]).copy()
        if sub.empty:
            continue

        for c in ["WWR", "Complexity", "Position", "ExperienceGroup", "SportFreqGroup", "Repetition"]:
            sub[c] = sub[c].astype(str)

        formula = (
            f"{dv} ~ C(WWR) * C(Complexity) + C(ExperienceGroup) + C(SportFreqGroup) + C(Repetition) + C(Position)"
        )

        fit, fit_info = _fit_with_fallback(sub, formula)

        coef = _coef_table(fit)
        coef.insert(0, "DV", dv)
        all_coefs.append(coef)

        model_log.append({
            "DV": dv,
            "formula": formula,
            "fit_method": fit_info["fit_method"],
            "re_formula_used": fit_info["re_formula_used"] if fit_info["re_formula_used"] else "1",
            "fallback_to_random_intercept": fit_info["fallback_to_random_intercept"],
            "converged": fit_info["converged"],
            "n_rows": int(len(sub)),
            "n_subjects": int(sub["SubjectID"].nunique()),
        })

        # consistency uses numeric repetition
        csub = df.dropna(subset=["SubjectID", dv, "SceneID", "Repetition", "SportFreqGroup"]).copy()
        cdf = subject_consistency(csub, dv)
        cdf = cdf.merge(csub[["SubjectID", "SportFreqGroup", "ExperienceGroup"]].drop_duplicates(), on="SubjectID", how="left")
        consistency_all.append(cdf)

    if not all_coefs:
        raise SystemExit("No analyzable DV found.")

    coef_df = pd.concat(all_coefs, ignore_index=True)
    coef_df.to_csv(out / "table_fixed_effects_all_dv.csv", index=False, encoding="utf-8-sig")

    key = coef_df[coef_df["Term"].str.contains("C\(WWR\)|C\(Complexity\)|C\(SportFreqGroup\)|C\(ExperienceGroup\)|C\(Repetition\)", regex=True, na=False)].copy()
    key.to_csv(out / "table_main_interactions_all_dv.csv", index=False, encoding="utf-8-sig")

    model_log_df = pd.DataFrame(model_log)
    model_log_df.to_csv(out / "model_log.csv", index=False, encoding="utf-8-sig")

    cons_df = pd.concat(consistency_all, ignore_index=True)
    cons_df.to_csv(out / "round_consistency_by_subject.csv", index=False, encoding="utf-8-sig")

    cons_grp = cons_df.groupby(["dv", "SportFreqGroup", "ExperienceGroup"], dropna=False).agg(
        n=("SubjectID", "nunique"),
        corr_mean=("corr_r1_r2", "mean"),
        corr_sd=("corr_r1_r2", "std"),
        sd_change_mean=("sd_change", "mean"),
        delta_mean=("mean_delta_r2_minus_r1", "mean"),
    ).reset_index()
    cons_grp.to_csv(out / "round_consistency_by_group.csv", index=False, encoding="utf-8-sig")

    # Figure 1: heatmap mean Afford5 by WWR×Complexity, faceted by SportFreqGroup
    h = df.dropna(subset=["Afford5", "WWR", "Complexity", "SportFreqGroup"]).copy()
    for fg, g in h.groupby("SportFreqGroup"):
        piv = g.pivot_table(index="Complexity", columns="WWR", values="Afford5", aggfunc="mean")
        plt.figure(figsize=(5, 4))
        sns.heatmap(piv, annot=True, fmt=".2f", cmap="YlGnBu")
        plt.title(f"Afford5 Mean Heatmap ({fg})")
        plt.tight_layout()
        plt.savefig(out / "figures" / f"heatmap_afford5_{fg}.png", dpi=220)
        plt.close()

    # Figure 2: interaction line x=WWR hue=Complexity col=SportFreqGroup
    g = df.dropna(subset=["Afford5", "WWR", "Complexity", "SportFreqGroup"]).copy()
    g["WWR"] = g["WWR"].astype(int).astype(str)
    g["Complexity"] = g["Complexity"].map({0: "C0", 1: "C1"}).fillna(g["Complexity"].astype(str))
    p = sns.catplot(data=g, x="WWR", y="Afford5", hue="Complexity", col="SportFreqGroup", kind="point", errorbar="se", dodge=True, height=4, aspect=1)
    p.fig.suptitle("WWR × Complexity on Afford5 by Sport Frequency Group", y=1.05)
    p.savefig(out / "figures" / "interaction_afford5_by_sportfreqgroup.png", dpi=220)
    plt.close('all')

    # Figure 3: Round1 vs Round2 difference by group
    d = df.dropna(subset=["Afford5", "SubjectID", "SceneID", "Repetition", "SportFreqGroup"]).copy()
    piv = d.pivot_table(index=["SubjectID", "SceneID", "SportFreqGroup"], columns="Repetition", values="Afford5", aggfunc="mean").reset_index()
    if 1 in piv.columns and 2 in piv.columns:
        piv["Diff_R2_minus_R1"] = piv[2] - piv[1]
        plt.figure(figsize=(6, 4))
        sns.boxplot(data=piv, x="SportFreqGroup", y="Diff_R2_minus_R1")
        sns.stripplot(data=piv, x="SportFreqGroup", y="Diff_R2_minus_R1", color="black", alpha=0.35, size=3)
        plt.title("Round2 - Round1 (Afford5) by Sport Frequency Group")
        plt.tight_layout()
        plt.savefig(out / "figures" / "round_diff_afford5_by_sportfreqgroup.png", dpi=220)
        plt.close()

    summary = {
        "outputs": [
            "table_fixed_effects_all_dv.csv",
            "table_main_interactions_all_dv.csv",
            "model_log.csv",
            "round_consistency_by_subject.csv",
            "round_consistency_by_group.csv",
            "figures/heatmap_afford5_*.png",
            "figures/interaction_afford5_by_sportfreqgroup.png",
            "figures/round_diff_afford5_by_sportfreqgroup.png",
        ]
    }
    (out / "analysis_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
