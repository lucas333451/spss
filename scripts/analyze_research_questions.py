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

# Item-level only (remove Afford4/Afford5 from research analyses)
# Use raw S5 (9-point) by default; S5_7 remains optional in long data for aligned-display use.
DVS = ["S1", "S2", "S3", "S4", "S5"]


# -----------------------------
# helpers
# -----------------------------
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
                "aic": float(fit.aic) if pd.notna(fit.aic) else np.nan,
                "bic": float(fit.bic) if pd.notna(fit.bic) else np.nan,
                "llf": float(fit.llf) if pd.notna(fit.llf) else np.nan,
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


def group_item_variance(df: pd.DataFrame, dvs: list[str]) -> pd.DataFrame:
    rows = []
    for dv in dvs:
        if dv not in df.columns:
            continue
        sub = df.dropna(subset=[dv, "SportFreqGroup", "ExperienceGroup", "SubjectID"])
        if sub.empty:
            continue

        global_sd = float(sub[dv].std(ddof=1)) if sub[dv].notna().sum() >= 2 else np.nan
        for (fg, eg), g in sub.groupby(["SportFreqGroup", "ExperienceGroup"], dropna=False):
            vals = g[dv].dropna().to_numpy(dtype=float)
            if len(vals) < 2:
                sd = np.nan
                iqr = np.nan
            else:
                sd = float(np.std(vals, ddof=1))
                q1, q3 = np.percentile(vals, [25, 75])
                iqr = float(q3 - q1)
            mean = float(np.mean(vals)) if len(vals) else np.nan
            cv = float(sd / mean) if (pd.notna(sd) and pd.notna(mean) and mean != 0) else np.nan

            # variance warning rules for 1-9 Likert-like scale
            high_abs = bool(pd.notna(sd) and sd >= 1.5)
            high_rel = bool(pd.notna(sd) and pd.notna(global_sd) and sd >= 1.25 * global_sd)

            rows.append({
                "DV": dv,
                "SportFreqGroup": fg,
                "ExperienceGroup": eg,
                "n_rows": int(len(vals)),
                "n_subjects": int(g["SubjectID"].nunique()),
                "mean": mean,
                "sd": sd,
                "iqr": iqr,
                "cv": cv,
                "global_sd_dv": global_sd,
                "high_variance_abs_sd_ge_1p5": high_abs,
                "high_variance_rel_sd_ge_1p25x_global": high_rel,
                "high_variance_flag": bool(high_abs or high_rel),
            })

    out = pd.DataFrame(rows)
    if not out.empty:
        out = out.sort_values(["DV", "high_variance_flag", "sd"], ascending=[True, False, False]).reset_index(drop=True)
    return out


# -----------------------------
# main
# -----------------------------
def main():
    ap = argparse.ArgumentParser(description="Angle1+Angle2 item-level analysis for WWR×Complexity with frequency and repetition")
    ap.add_argument("--long-csv", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, default=Path("results/research"))
    args = ap.parse_args()

    out = args.out_dir
    out.mkdir(parents=True, exist_ok=True)
    (out / "figures").mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(args.long_csv)

    required_cols = ["SubjectID", "WWR", "Complexity", "Position", "S1", "S2", "S3", "S4", "S5"]
    for c in required_cols:
        if c not in df.columns:
            raise SystemExit(f"Missing required column: {c}")

    if "ExperienceGroup" not in df.columns:
        df["ExperienceGroup"] = "Unknown"
    if "SportFreqGroup" not in df.columns:
        df["SportFreqGroup"] = "Unknown"
    if "Repetition" not in df.columns:
        df["Repetition"] = df["Block"] if "Block" in df.columns else np.nan

    # numeric harmonization for figures/consistency
    df["WWR"] = pd.to_numeric(df["WWR"], errors="coerce")
    df["Complexity"] = pd.to_numeric(df["Complexity"], errors="coerce")
    df["Position"] = pd.to_numeric(df["Position"], errors="coerce")
    df["Repetition"] = pd.to_numeric(df["Repetition"], errors="coerce")

    angle1_all = []
    angle2_all = []
    model_log = []
    consistency_all = []

    for dv in DVS:
        sub = df.dropna(subset=["SubjectID", dv, "WWR", "Complexity", "Position", "ExperienceGroup", "SportFreqGroup", "Repetition"]).copy()
        if sub.empty:
            continue

        for c in ["WWR", "Complexity", "Position", "ExperienceGroup", "SportFreqGroup", "Repetition"]:
            sub[c] = sub[c].astype(str)

        # Angle 1: main effects + interaction sensitivity by frequency
        formula_a1 = (
            f"{dv} ~ C(WWR) * C(Complexity) * C(SportFreqGroup) + "
            f"C(ExperienceGroup) + C(Repetition) + C(Position)"
        )
        fit_a1, info_a1 = _fit_with_fallback(sub, formula_a1)
        coef_a1 = _coef_table(fit_a1)
        coef_a1.insert(0, "DV", dv)
        coef_a1.insert(1, "Angle", "Angle1_main_interaction")
        coef_a1.insert(2, "Formula", formula_a1)
        angle1_all.append(coef_a1)

        model_log.append({
            "DV": dv,
            "Angle": "Angle1_main_interaction",
            "formula": formula_a1,
            "fit_method": info_a1["fit_method"],
            "re_formula_used": info_a1["re_formula_used"] if info_a1["re_formula_used"] else "1",
            "fallback_to_random_intercept": info_a1["fallback_to_random_intercept"],
            "converged": info_a1["converged"],
            "AIC": info_a1["aic"],
            "BIC": info_a1["bic"],
            "LogLik": info_a1["llf"],
            "n_rows": int(len(sub)),
            "n_subjects": int(sub["SubjectID"].nunique()),
        })

        # Angle 2: round-based convergence / habituation / learning
        formula_a2 = (
            f"{dv} ~ C(Repetition) * C(WWR) * C(Complexity) * C(SportFreqGroup) + "
            f"C(ExperienceGroup) + C(Position)"
        )
        fit_a2, info_a2 = _fit_with_fallback(sub, formula_a2)
        coef_a2 = _coef_table(fit_a2)
        coef_a2.insert(0, "DV", dv)
        coef_a2.insert(1, "Angle", "Angle2_round_convergence")
        coef_a2.insert(2, "Formula", formula_a2)
        angle2_all.append(coef_a2)

        model_log.append({
            "DV": dv,
            "Angle": "Angle2_round_convergence",
            "formula": formula_a2,
            "fit_method": info_a2["fit_method"],
            "re_formula_used": info_a2["re_formula_used"] if info_a2["re_formula_used"] else "1",
            "fallback_to_random_intercept": info_a2["fallback_to_random_intercept"],
            "converged": info_a2["converged"],
            "AIC": info_a2["aic"],
            "BIC": info_a2["bic"],
            "LogLik": info_a2["llf"],
            "n_rows": int(len(sub)),
            "n_subjects": int(sub["SubjectID"].nunique()),
        })

        # consistency stats (correlation + delta + variance change)
        csub = df.dropna(subset=["SubjectID", dv, "SceneID", "Repetition", "SportFreqGroup"]).copy()
        cdf = subject_consistency(csub, dv)
        cdf = cdf.merge(csub[["SubjectID", "SportFreqGroup", "ExperienceGroup"]].drop_duplicates(), on="SubjectID", how="left")
        consistency_all.append(cdf)

    if not angle1_all and not angle2_all:
        raise SystemExit("No analyzable DV found.")

    angle1_df = pd.concat(angle1_all, ignore_index=True) if angle1_all else pd.DataFrame()
    angle2_df = pd.concat(angle2_all, ignore_index=True) if angle2_all else pd.DataFrame()

    # Backward-compatible combined table
    all_coef_df = pd.concat([x for x in [angle1_df, angle2_df] if not x.empty], ignore_index=True)
    all_coef_df.to_csv(out / "table_fixed_effects_all_dv.csv", index=False, encoding="utf-8-sig")

    if not angle1_df.empty:
        angle1_df.to_csv(out / "table_angle1_effects_all_dv.csv", index=False, encoding="utf-8-sig")
        key1 = angle1_df[
            angle1_df["Term"].str.contains("C\(WWR\)|C\(Complexity\)|C\(SportFreqGroup\)", regex=True, na=False)
        ].copy()
        key1.to_csv(out / "table_angle1_main_interactions_all_dv.csv", index=False, encoding="utf-8-sig")

    if not angle2_df.empty:
        angle2_df.to_csv(out / "table_angle2_effects_all_dv.csv", index=False, encoding="utf-8-sig")
        key2 = angle2_df[
            angle2_df["Term"].str.contains("C\(Repetition\)|C\(WWR\)|C\(Complexity\)|C\(SportFreqGroup\)", regex=True, na=False)
        ].copy()
        key2.to_csv(out / "table_angle2_round_interactions_all_dv.csv", index=False, encoding="utf-8-sig")

    # Legacy file name kept for compatibility
    key_legacy = all_coef_df[
        all_coef_df["Term"].str.contains("C\(WWR\)|C\(Complexity\)|C\(SportFreqGroup\)|C\(ExperienceGroup\)|C\(Repetition\)", regex=True, na=False)
    ].copy()
    key_legacy.to_csv(out / "table_main_interactions_all_dv.csv", index=False, encoding="utf-8-sig")

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

    # new: same-group item variance check
    var_df = group_item_variance(df, DVS)
    var_df.to_csv(out / "item_variance_by_group.csv", index=False, encoding="utf-8-sig")

    if not var_df.empty:
        var_summary = (
            var_df.groupby(["DV", "SportFreqGroup", "ExperienceGroup"], dropna=False)
            .agg(
                n_rows=("n_rows", "sum"),
                n_subjects=("n_subjects", "max"),
                mean_sd=("sd", "mean"),
                max_sd=("sd", "max"),
                any_high_variance=("high_variance_flag", "max"),
            )
            .reset_index()
        )
    else:
        var_summary = pd.DataFrame(columns=["DV", "SportFreqGroup", "ExperienceGroup", "n_rows", "n_subjects", "mean_sd", "max_sd", "any_high_variance"])
    var_summary.to_csv(out / "item_variance_summary_by_group.csv", index=False, encoding="utf-8-sig")

    # Figure 1+2+3 for EACH item (S1-S5)
    for dv in DVS:
        if dv not in df.columns:
            continue

        # heatmap mean by WWR×Complexity, faceted by frequency group
        h = df.dropna(subset=[dv, "WWR", "Complexity", "SportFreqGroup"]).copy()
        for fg, g in h.groupby("SportFreqGroup"):
            piv = g.pivot_table(index="Complexity", columns="WWR", values=dv, aggfunc="mean")
            plt.figure(figsize=(5, 4))
            sns.heatmap(piv, annot=True, fmt=".2f", cmap="YlGnBu")
            plt.title(f"{dv} Mean Heatmap ({fg})")
            plt.tight_layout()
            plt.savefig(out / "figures" / f"heatmap_{dv}_{fg}.png", dpi=220)
            plt.close()

        # interaction line
        g = df.dropna(subset=[dv, "WWR", "Complexity", "SportFreqGroup"]).copy()
        g["WWR"] = g["WWR"].astype(int).astype(str)
        g["Complexity"] = g["Complexity"].map({0: "C0", 1: "C1"}).fillna(g["Complexity"].astype(str))
        p = sns.catplot(
            data=g,
            x="WWR",
            y=dv,
            hue="Complexity",
            col="SportFreqGroup",
            kind="point",
            errorbar="se",
            dodge=True,
            height=4,
            aspect=1,
        )
        p.fig.suptitle(f"WWR × Complexity on {dv} by Sport Frequency Group", y=1.05)
        p.savefig(out / "figures" / f"interaction_{dv}_by_sportfreqgroup.png", dpi=220)
        plt.close('all')

        # Round diff boxplot
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
