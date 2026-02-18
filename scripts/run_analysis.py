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
from scipy.stats import ttest_rel
from statsmodels.formula.api import mixedlm
from statsmodels.stats.multitest import multipletests
from numpy.linalg import LinAlgError

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
        if term.startswith("Group Var") or " Var" in term or " Cov" in term:
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
    if term == "Intercept":
        return "Control", "Intercept"

    n_int = term.count(":")
    if n_int == 0:
        if any(x in term for x in ["C(WWR)", "C(Complexity)", "C(ExperienceGroup)", "C(SportFreqGroup)", "C(Repetition)"]):
            return "Main Effect", term
        return "Control", term
    if n_int == 1:
        return "Interaction (2-way)", term
    if n_int == 2:
        return "Interaction (3-way)", term
    if n_int >= 3:
        return "Interaction (4-way+)", term
    return "Other", term


def _humanize_term(term: str) -> str:
    t = str(term)
    mapping = {
        "Intercept": "Intercept",
        "C(WWR)[T.15]": "WWR: 15 (vs reference)",
        "C(WWR)[T.45]": "WWR: 45 (vs reference)",
        "C(WWR)[T.75]": "WWR: 75 (vs reference)",
        "C(Complexity)[T.1]": "Complexity: High/C1 (vs Low/C0)",
        "C(Complexity)[T.0]": "Complexity: Low/C0 (vs High/C1)",
        "C(Repetition)[T.2]": "Repetition: Round2 (vs Round1)",
    }
    if t in mapping:
        return mapping[t]

    t = t.replace("C(ExperienceGroup)[T.", "Experience group: ")
    t = t.replace("C(SportFreqGroup)[T.", "Sport frequency group: ")
    t = t.replace("C(Repetition)[T.", "Repetition: Round")
    t = t.replace('C(WWR)[T.', 'WWR: ')
    t = t.replace('C(Complexity)[T.', 'Complexity: ')
    t = t.replace('C(Position)[T.', 'Position: ')
    t = t.replace(']', ' (vs reference)')
    t = t.replace(':', ' × ')
    t = t.replace('Complexity: 1 (vs reference)', 'Complexity: High/C1 (vs Low/C0)')
    t = t.replace('Complexity: 0 (vs reference)', 'Complexity: Low/C0 (vs High/C1)')
    return t


def _to_markdown_table(df: pd.DataFrame, float_cols=None, digits=3) -> str:
    x = df.copy()
    if float_cols is None:
        float_cols = [c for c in x.columns if pd.api.types.is_numeric_dtype(x[c])]
    for c in float_cols:
        x[c] = x[c].map(lambda v: f"{v:.{digits}f}" if pd.notna(v) else "")
    return x.to_markdown(index=False)


def _fit_with_fallback(data: pd.DataFrame, formula: str, re_formula: str | None) -> tuple[object, dict]:
    attempts = [
        {"method": "lbfgs", "re_formula": re_formula},
        {"method": "powell", "re_formula": re_formula},
    ]
    if re_formula is not None:
        attempts.extend([
            {"method": "lbfgs", "re_formula": None},
            {"method": "powell", "re_formula": None},
        ])

    last_err = None
    for a in attempts:
        try:
            mdl = mixedlm(formula=formula, data=data, groups=data["SubjectID"], re_formula=a["re_formula"])
            fit = mdl.fit(reml=False, method=a["method"], maxiter=2000)
            info = {
                "method": a["method"],
                "re_formula_requested": re_formula,
                "re_formula_used": a["re_formula"],
                "fallback_used": bool(a["re_formula"] != re_formula),
                "converged": bool(getattr(fit, "converged", True)),
                "aic": float(fit.aic) if pd.notna(fit.aic) else np.nan,
                "bic": float(fit.bic) if pd.notna(fit.bic) else np.nan,
                "llf": float(fit.llf) if pd.notna(fit.llf) else np.nan,
            }
            return fit, info
        except Exception as e:
            last_err = str(e)
            continue

    raise RuntimeError(f"MixedLM fit failed for formula={formula}; last_error={last_err}")


def _build_model_comparison(model_df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    # A: compact main effects
    f_a = "Afford5 ~ C(Complexity) + C(WWR) + C(ExperienceGroup) + C(SportFreqGroup) + C(Repetition) + C(Position)"
    # B: key interaction
    f_b = "Afford5 ~ C(Complexity) * C(WWR) + C(ExperienceGroup) + C(SportFreqGroup) + C(Repetition) + C(Position)"
    # C: fuller model
    f_c = "Afford5 ~ C(WWR) * C(Complexity) * C(ExperienceGroup) * C(SportFreqGroup) + C(Repetition) + C(Position)"

    models = [
        ("Model_A_compact", f_a),
        ("Model_B_key_interaction", f_b),
        ("Model_C_full", f_c),
    ]

    rows = []
    fitted = {}
    for name, formula in models:
        fit, info = _fit_with_fallback(model_df, formula, re_formula="1 + C(Complexity)")
        rows.append({
            "Model": name,
            "Formula": formula,
            "RandomStructureRequested": "(1 + Complexity | Subject)",
            "RandomStructureUsed": "(1 + Complexity | Subject)" if info["re_formula_used"] else "(1 | Subject)",
            "FitMethod": info["method"],
            "FallbackToRandomIntercept": info["fallback_used"],
            "Converged": info["converged"],
            "AIC": info["aic"],
            "BIC": info["bic"],
            "LogLik": info["llf"],
            "n_rows": int(len(model_df)),
            "n_subjects": int(model_df["SubjectID"].nunique()),
        })
        fitted[name] = (fit, info)

    cmp_df = pd.DataFrame(rows).sort_values(["AIC", "BIC"], na_position="last").reset_index(drop=True)
    best_name = cmp_df.iloc[0]["Model"]
    best_fit, best_info = fitted[best_name]

    pick = {
        "recommended_model": best_name,
        "recommended_formula": cmp_df.iloc[0]["Formula"],
        "random_structure_used": cmp_df.iloc[0]["RandomStructureUsed"],
        "fit_method": cmp_df.iloc[0]["FitMethod"],
        "aic": float(cmp_df.iloc[0]["AIC"]),
        "bic": float(cmp_df.iloc[0]["BIC"]),
    }
    return cmp_df, {"fit": best_fit, "info": best_info, **pick}


def _paired_cohens_d(a: np.ndarray, b: np.ndarray) -> float:
    diff = b - a
    sd = np.std(diff, ddof=1)
    if np.isnan(sd) or sd == 0:
        return np.nan
    return float(np.mean(diff) / sd)


def _simple_effects_by_wwr(model_df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for w in sorted(model_df["WWR"].astype(str).unique(), key=lambda x: int(float(x)) if str(x).replace('.', '', 1).isdigit() else x):
        sub = model_df[model_df["WWR"].astype(str) == str(w)].copy()

        piv = sub.pivot_table(index="SubjectID", columns="Complexity", values="Afford5", aggfunc="mean")
        if "0" in piv.columns and "1" in piv.columns:
            x0 = piv["0"].to_numpy(dtype=float)
            x1 = piv["1"].to_numpy(dtype=float)
        else:
            # try numeric-coded columns fallback
            ccols = list(piv.columns)
            has0 = 0 in ccols
            has1 = 1 in ccols
            if has0 and has1:
                x0 = piv[0].to_numpy(dtype=float)
                x1 = piv[1].to_numpy(dtype=float)
            else:
                continue

        mask = np.isfinite(x0) & np.isfinite(x1)
        if mask.sum() < 3:
            continue

        t_res = ttest_rel(x1[mask], x0[mask], nan_policy="omit")
        mean_c0 = float(np.mean(x0[mask]))
        mean_c1 = float(np.mean(x1[mask]))
        d_z = _paired_cohens_d(x0[mask], x1[mask])

        rows.append({
            "WWR": w,
            "n_subjects": int(mask.sum()),
            "Mean_C0": mean_c0,
            "Mean_C1": mean_c1,
            "Delta_C1_minus_C0": mean_c1 - mean_c0,
            "t": float(t_res.statistic),
            "p": float(t_res.pvalue),
            "cohens_dz": d_z,
        })

    out = pd.DataFrame(rows)
    if out.empty:
        return out

    rej, p_adj, _, _ = multipletests(out["p"].to_numpy(), method="holm")
    out["p_holm"] = p_adj
    out["Sig_holm"] = np.where(out["p_holm"] < 0.001, "***", np.where(out["p_holm"] < 0.01, "**", np.where(out["p_holm"] < 0.05, "*", "")))
    out["Significant_holm"] = rej
    return out


def _build_paper_tables(model_df: pd.DataFrame, coef_df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    desc = (
        model_df.groupby(["WWR", "Complexity", "ExperienceGroup", "SportFreqGroup", "Repetition"], dropna=False)["Afford5"]
        .agg(N="count", Mean="mean", SD="std")
        .reset_index()
    )

    fixed = coef_df.copy()
    fixed[["EffectType", "Effect"]] = fixed["Term"].apply(lambda t: pd.Series(_classify_effect(str(t))))
    fixed["APA_Term"] = fixed["Effect"].apply(_humanize_term)
    fixed = fixed[["EffectType", "Effect", "APA_Term", "Coef", "SE", "z", "p", "Sig", "CI95_low", "CI95_high"]]
    fixed = fixed.sort_values(["EffectType", "Effect"]).reset_index(drop=True)

    infer = fixed[fixed["EffectType"].isin(["Main Effect", "Interaction (2-way)", "Interaction (3-way)", "Interaction (4-way+)"])].copy()
    infer = infer.rename(columns={"Effect": "Term"})
    infer["APA_Term"] = infer["Term"].apply(_humanize_term)
    infer = infer[["EffectType", "Term", "APA_Term", "Coef", "SE", "z", "p", "Sig", "CI95_low", "CI95_high"]]

    return desc, fixed, infer


def _auto_results_draft_zh(best: dict, infer_df: pd.DataFrame, simple_df: pd.DataFrame) -> str:
    lines = [
        "# 论文结果段草稿（自动生成，中文）",
        "",
        "## 模型说明",
        f"采用线性混合模型（LMM），推荐模型为：`{best['recommended_formula']}`。",
        f"随机结构使用：`{best['random_structure_used']}`（拟合方法：{best['fit_method']}）。",
        "",
        "## 主要结果（固定效应）",
    ]

    sig = infer_df[infer_df["p"] < 0.05].copy() if not infer_df.empty else pd.DataFrame()
    if sig.empty:
        lines.append("在当前模型下，主要固定效应与交互项未达到显著水平（p < .05）。")
    else:
        for _, r in sig.sort_values("p").head(8).iterrows():
            lines.append(
                f"- {r['APA_Term']}：β={r['Coef']:.3f}, SE={r['SE']:.3f}, z={r['z']:.3f}, p={r['p']:.4f}{r['Sig']}。"
            )

    lines.extend(["", "## Simple effect（Complexity 在各 WWR 下）"])
    if simple_df.empty:
        lines.append("未能得到可分析的 simple effect 结果。")
    else:
        sig_s = simple_df[simple_df["p_holm"] < 0.05].copy()
        if sig_s.empty:
            lines.append("在 Holm 多重比较校正后，各 WWR 条件下 Complexity 的 simple effect 均不显著。")
        else:
            for _, r in sig_s.iterrows():
                lines.append(
                    f"- WWR={r['WWR']}：C1-C0={r['Delta_C1_minus_C0']:.3f}, t={r['t']:.3f}, p_holm={r['p_holm']:.4f}{r['Sig_holm']}, d_z={r['cohens_dz']:.3f}。"
                )

    lines.extend([
        "",
        "## 写作提示",
        "请将上述自动草稿与理论假设、研究设计、图表编号进行人工核对后再用于论文正文。",
    ])
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="Run LMM on long-format questionnaire data and export paper-ready tables")
    ap.add_argument("--long-csv", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, default=Path("results/model"))
    args = ap.parse_args()

    out = args.out_dir
    out.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(args.long_csv)
    alpha = cronbach_alpha(df[["S1", "S2", "S3", "S4", "S5"]])

    if "ExperienceGroup" not in df.columns:
        raise SystemExit("Missing ExperienceGroup in long CSV. Please re-run transform_wide_to_long.py with latest version.")
    if "SportFreqGroup" not in df.columns:
        raise SystemExit("Missing SportFreqGroup in long CSV. Please re-run transform_wide_to_long.py with latest version.")

    # Repetition compatibility: prefer explicit column, fallback to Block
    if "Repetition" not in df.columns:
        df["Repetition"] = df["Block"]

    keep_cols = ["SubjectID", "Afford5", "WWR", "Complexity", "Position", "ExperienceGroup", "SportFreqGroup", "Repetition"]
    model_df = df.dropna(subset=keep_cols).copy()

    # categorical coding
    for c in ["WWR", "Complexity", "Position", "ExperienceGroup", "SportFreqGroup", "Repetition"]:
        model_df[c] = model_df[c].astype(str)

    # model selection (A/B/C)
    cmp_df, best = _build_model_comparison(model_df)
    fit = best["fit"]
    fit_info = best["info"]

    coef_df = _extract_coef_table(fit)
    desc_df, fixed_df, infer_df = _build_paper_tables(model_df, coef_df)

    # simple effects under each WWR
    simple_df = _simple_effects_by_wwr(model_df)

    # interaction plot with repetition as style
    plt.figure(figsize=(9, 5))
    pdat = model_df.copy()
    pdat["Complexity"] = pdat["Complexity"].replace({"0": "C0", "1": "C1"})
    sns.pointplot(data=pdat, x="WWR", y="Afford5", hue="Complexity", errorbar="se", dodge=True)
    plt.title("WWR × Complexity on Afford5")
    plt.tight_layout()
    (out / "figures").mkdir(parents=True, exist_ok=True)
    plt.savefig(out / "figures" / "wwr_complexity_afford5.png", dpi=220)
    plt.close()

    # save outputs
    (out / "lmm_summary.txt").write_text(str(fit.summary()), encoding="utf-8")
    (out / "model_formula.txt").write_text(str(best["recommended_formula"]), encoding="utf-8")
    cmp_df.to_csv(out / "model_comparison.csv", index=False, encoding="utf-8-sig")
    desc_df.to_csv(out / "table_descriptives.csv", index=False, encoding="utf-8-sig")
    fixed_df.to_csv(out / "table_fixed_effects.csv", index=False, encoding="utf-8-sig")
    infer_df.to_csv(out / "table_main_interactions.csv", index=False, encoding="utf-8-sig")
    simple_df.to_csv(out / "table_simple_effects_complexity_by_wwr.csv", index=False, encoding="utf-8-sig")

    md_lines = [
        "# Paper-ready Results Tables",
        "",
        "## Table 0. Model comparison (A/B/C)",
        _to_markdown_table(cmp_df),
        "",
        "## Table 1. Descriptive statistics by condition",
        _to_markdown_table(desc_df),
        "",
        "## Table 2. Fixed effects coefficients (recommended LMM)",
        _to_markdown_table(fixed_df),
        "",
        "## Table 3. Main and interaction effects (compact)",
        _to_markdown_table(infer_df),
        "",
        "## Table 4. Simple effects: Complexity (C1 vs C0) within each WWR",
        _to_markdown_table(simple_df) if not simple_df.empty else "No analyzable simple-effects rows.",
        "",
        f"Reliability (Cronbach's alpha, S1-S5): {alpha:.3f}" if not np.isnan(alpha) else "Reliability: NA",
        "",
        f"Recommended model: {best['recommended_model']}",
        f"Formula: {best['recommended_formula']}",
        f"Random structure used: {best['random_structure_used']}",
    ]
    (out / "paper_tables.md").write_text("\n".join(md_lines), encoding="utf-8")

    draft_zh = _auto_results_draft_zh(best, infer_df, simple_df)
    (out / "results_draft_zh.md").write_text(draft_zh, encoding="utf-8")

    report = {
        "n_rows_input": int(len(df)),
        "n_rows_model": int(len(model_df)),
        "n_subjects": int(model_df["SubjectID"].nunique()),
        "cronbach_alpha_s1_s5": None if np.isnan(alpha) else float(alpha),
        "recommended_model": best["recommended_model"],
        "formula": best["recommended_formula"],
        "random_structure_requested": "(1 + Complexity | Subject)",
        "random_structure_used": best["random_structure_used"],
        "fit_method": best["fit_method"],
        "fit_fallback_to_random_intercept": bool(fit_info.get("fallback_used", False)),
        "outputs": {
            "model_comparison_csv": str(out / "model_comparison.csv"),
            "table_descriptives_csv": str(out / "table_descriptives.csv"),
            "table_fixed_effects_csv": str(out / "table_fixed_effects.csv"),
            "table_main_interactions_csv": str(out / "table_main_interactions.csv"),
            "table_simple_effects_csv": str(out / "table_simple_effects_complexity_by_wwr.csv"),
            "paper_tables_md": str(out / "paper_tables.md"),
            "results_draft_zh_md": str(out / "results_draft_zh.md"),
        },
    }
    (out / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
