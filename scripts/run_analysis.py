#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import argparse
import json
import warnings

import numpy as np
import pandas as pd
import pingouin as pg
import seaborn as sns
import matplotlib.pyplot as plt
from statsmodels.formula.api import mixedlm

warnings.filterwarnings("ignore")


def cronbach_alpha(df: pd.DataFrame) -> float:
    x = df.dropna()
    if x.shape[0] < 3 or x.shape[1] < 2:
        return np.nan
    return float(pg.cronbach_alpha(data=x)[0])


def _extract_coef_table(fit) -> pd.DataFrame:
    params = fit.params
    bse = fit.bse
    zvals = fit.tvalues
    pvals = fit.pvalues
    ci = fit.conf_int()

    rows = []
    for term in params.index:
        if term == "Group Var":
            continue
        rows.append(
            {
                "Term": term,
                "Coef": params[term],
                "SE": bse[term],
                "z": zvals[term],
                "p": pvals[term],
                "CI95_low": ci.loc[term, 0] if term in ci.index else np.nan,
                "CI95_high": ci.loc[term, 1] if term in ci.index else np.nan,
            }
        )
    df = pd.DataFrame(rows)

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

    df["Sig"] = df["p"].apply(sigstar)
    return df


def _classify_effect(term: str) -> tuple[str, str]:
    # main / interaction(2-way/3-way) / control
    if term == "Intercept":
        return "Control", "Intercept"

    n_int = term.count(":")
    if n_int == 0:
        # fixed main effects + controls
        if any(x in term for x in ["C(WWR)", "C(Complexity)", "C(SportFreq)"]):
            return "Main Effect", term
        return "Control", term
    if n_int == 1:
        return "Interaction (2-way)", term
    if n_int >= 2:
        return "Interaction (3-way)", term
    return "Other", term


def _build_paper_tables(model_df: pd.DataFrame, coef_df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    # Table A: descriptive stats by condition
    desc = (
        model_df.groupby(["WWR", "Complexity", "SportFreq"], dropna=False)["Afford5"]
        .agg(N="count", Mean="mean", SD="std")
        .reset_index()
    )

    # Table B: fixed effect coefficients (publication-friendly)
    fixed = coef_df.copy()
    fixed[["EffectType", "Effect"]] = fixed["Term"].apply(lambda t: pd.Series(_classify_effect(str(t))))
    fixed = fixed[["EffectType", "Effect", "Coef", "SE", "z", "p", "Sig", "CI95_low", "CI95_high"]]
    fixed = fixed.sort_values(["EffectType", "Effect"]).reset_index(drop=True)

    # Table C: compact inferential summary (main/interactions only)
    infer = fixed[fixed["EffectType"].isin(["Main Effect", "Interaction (2-way)", "Interaction (3-way)"])].copy()
    infer = infer.rename(columns={"Effect": "Term"})
    infer = infer[["EffectType", "Term", "Coef", "SE", "z", "p", "Sig", "CI95_low", "CI95_high"]]

    return desc, fixed, infer


def _to_markdown_table(df: pd.DataFrame, float_cols=None, digits=3) -> str:
    x = df.copy()
    if float_cols is None:
        float_cols = [c for c in x.columns if pd.api.types.is_numeric_dtype(x[c])]
    for c in float_cols:
        x[c] = x[c].map(lambda v: f"{v:.{digits}f}" if pd.notna(v) else "")
    return x.to_markdown(index=False)


def main():
    ap = argparse.ArgumentParser(description="Run LMM on long-format questionnaire data and export paper-ready tables")
    ap.add_argument("--long-csv", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, default=Path("results/model"))
    args = ap.parse_args()

    out = args.out_dir
    out.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(args.long_csv)

    alpha = cronbach_alpha(df[["S1", "S2", "S3", "S4", "S5"]])

    model_df = df.dropna(subset=["SubjectID", "Afford5", "WWR", "Complexity", "SportFreq"]).copy()
    # Ensure categorical for reporting clarity
    model_df["WWR"] = model_df["WWR"].astype(str)
    model_df["Complexity"] = model_df["Complexity"].astype(str)
    model_df["SportFreq"] = model_df["SportFreq"].astype(str)
    model_df["Block"] = model_df["Block"].astype(str)
    model_df["Position"] = model_df["Position"].astype(str)

    formula = "Afford5 ~ C(WWR) * C(Complexity) * C(SportFreq) + C(Block) + C(Position)"
    fit = mixedlm(formula=formula, data=model_df, groups=model_df["SubjectID"]).fit(reml=False, method="lbfgs", maxiter=1000)

    coef_df = _extract_coef_table(fit)
    desc_df, fixed_df, infer_df = _build_paper_tables(model_df, coef_df)

    # interaction plot
    plt.figure(figsize=(8, 5))
    sns.pointplot(data=model_df, x="WWR", y="Afford5", hue="Complexity", errorbar="se", dodge=True)
    plt.title("WWR × Complexity on Afford5")
    plt.tight_layout()
    (out / "figures").mkdir(parents=True, exist_ok=True)
    plt.savefig(out / "figures" / "wwr_complexity_afford5.png", dpi=220)
    plt.close()

    # raw outputs
    (out / "lmm_summary.txt").write_text(str(fit.summary()), encoding="utf-8")
    (out / "model_formula.txt").write_text(formula, encoding="utf-8")

    # paper-ready csv
    desc_df.to_csv(out / "table_descriptives.csv", index=False, encoding="utf-8-sig")
    fixed_df.to_csv(out / "table_fixed_effects.csv", index=False, encoding="utf-8-sig")
    infer_df.to_csv(out / "table_main_interactions.csv", index=False, encoding="utf-8-sig")

    # markdown tables for direct manuscript paste
    md_lines = [
        "# Paper-ready Results Tables",
        "",
        "## Table 1. Descriptive statistics by condition",
        _to_markdown_table(desc_df),
        "",
        "## Table 2. Fixed effects coefficients (LMM)",
        _to_markdown_table(fixed_df),
        "",
        "## Table 3. Main and interaction effects (compact)",
        _to_markdown_table(infer_df),
        "",
        f"Reliability (Cronbach's alpha, S1-S5): {alpha:.3f}" if not np.isnan(alpha) else "Reliability: NA",
    ]
    (out / "paper_tables.md").write_text("\n".join(md_lines), encoding="utf-8")

    report = {
        "n_rows_input": int(len(df)),
        "n_rows_model": int(len(model_df)),
        "cronbach_alpha_s1_s5": None if np.isnan(alpha) else float(alpha),
        "formula": formula,
        "outputs": {
            "table_descriptives_csv": str(out / "table_descriptives.csv"),
            "table_fixed_effects_csv": str(out / "table_fixed_effects.csv"),
            "table_main_interactions_csv": str(out / "table_main_interactions.csv"),
            "paper_tables_md": str(out / "paper_tables.md"),
        },
    }
    (out / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
