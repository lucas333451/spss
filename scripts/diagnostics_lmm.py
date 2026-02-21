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
from scipy.stats import chi2
from statsmodels.formula.api import mixedlm


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



def _extract_coef_table(fit, model_name: str) -> pd.DataFrame:
    ci = fit.conf_int()
    rows = []
    for term in fit.params.index:
        if term.startswith("Group Var") or " Var" in term or " Cov" in term:
            continue
        rows.append({
            "Model": model_name,
            "Term": term,
            "Coef": fit.params[term],
            "SE": fit.bse[term],
            "z": fit.tvalues[term],
            "p": fit.pvalues[term],
            "Sig": _sigstar(fit.pvalues[term]),
            "CI95_low": ci.loc[term, 0] if term in ci.index else np.nan,
            "CI95_high": ci.loc[term, 1] if term in ci.index else np.nan,
        })
    return pd.DataFrame(rows)


def _is_singular_fit(fit, tol: float = 1e-8) -> bool:
    """Heuristic singular-fit detection for statsmodels MixedLM.

    A fit is treated as singular if random-effect covariance is near-singular
    (min eigenvalue <= tol) or any RE variance is ~0.

    Note: statsmodels may still mark such fits as converged; we flag them for audit.
    """
    if fit is None:
        return False
    cov_re = getattr(fit, "cov_re", None)
    if cov_re is None:
        return False
    try:
        arr = np.asarray(cov_re, dtype=float)
        if arr.ndim != 2 or arr.shape[0] == 0:
            return False
        # Diagonal variances ~ 0
        if np.any(np.diag(arr) <= tol):
            return True
        # Eigenvalues
        eig = np.linalg.eigvalsh(arr)
        if np.min(eig) <= tol:
            return True
    except Exception:
        return False
    return False


def _fit_with_fallback(data: pd.DataFrame, formula: str, re_formula: str | None):
    """Fit MixedLM with a conservative strategy.

    Strategy:
    - Try requested random structure with multiple optimizers.
    - If fit is singular, treat it as unacceptable and continue searching.
    - Fall back to random intercept-only if needed.

    Returns:
    - fit (or None)
    - info dict (includes convergence/singularity + warning capture)
    """

    attempts = [
        {"method": "lbfgs", "re_formula": re_formula},
        {"method": "powell", "re_formula": re_formula},
        {"method": "cg", "re_formula": re_formula},
        {"method": "lbfgs", "re_formula": None},
        {"method": "powell", "re_formula": None},
    ]

    last_err = None
    last_warn = ""

    for a in attempts:
        try:
            with warnings.catch_warnings(record=True) as wlist:
                warnings.simplefilter("always")
                mdl = mixedlm(formula=formula, data=data, groups=data["SubjectID"], re_formula=a["re_formula"])
                fit = mdl.fit(reml=False, method=a["method"], maxiter=3500)

            warn_msgs = sorted({str(w.message) for w in wlist})
            warn_join = " | ".join(warn_msgs)[:500]

            converged = bool(getattr(fit, "converged", True))
            singular = _is_singular_fit(fit)

            # Prefer non-singular solutions for audit cleanliness
            if singular:
                last_warn = warn_join or last_warn
                last_err = "singular_random_effects"
                continue

            return fit, {
                "fit_method": a["method"],
                "re_formula_used": a["re_formula"] if a["re_formula"] is not None else "1",
                "fallback_to_random_intercept": a["re_formula"] is None,
                "converged": converged,
                "singular": singular,
                "warnings": warn_join,
                "AIC": float(fit.aic) if pd.notna(fit.aic) else np.nan,
                "BIC": float(fit.bic) if pd.notna(fit.bic) else np.nan,
                "LogLik": float(fit.llf) if pd.notna(fit.llf) else np.nan,
                "df_modelwc": float(getattr(fit, "df_modelwc", np.nan)),
            }

        except Exception as e:
            last_err = str(e)
            continue

    return None, {
        "fit_method": None,
        "re_formula_used": re_formula if re_formula is not None else "1",
        "fallback_to_random_intercept": re_formula is None,
        "converged": False,
        "singular": True if last_err == "singular_random_effects" else False,
        "warnings": last_warn,
        "AIC": np.nan,
        "BIC": np.nan,
        "LogLik": np.nan,
        "df_modelwc": np.nan,
        "error": last_err,
    }


def _lrt_row(base_name, base_fit, full_name, full_fit):
    if base_fit is None or full_fit is None:
        return {
            "Compare": f"{full_name} vs {base_name}",
            "LR": np.nan,
            "df_diff": np.nan,
            "p": np.nan,
            "Significant": False,
        }

    lr = 2.0 * (full_fit.llf - base_fit.llf)
    df_diff = int(max(round(float(full_fit.df_modelwc - base_fit.df_modelwc)), 1))
    p = float(chi2.sf(lr, df_diff)) if lr >= 0 else np.nan
    return {
        "Compare": f"{full_name} vs {base_name}",
        "LR": float(lr),
        "df_diff": df_diff,
        "p": p,
        "Significant": bool(pd.notna(p) and p < 0.05),
    }


def _extract_random_variance(fit, label: str) -> pd.DataFrame:
    rows = []
    if fit is None:
        return pd.DataFrame([{"RandomStructure": label, "Component": "fit_failed", "Variance": np.nan}])

    # residual
    rows.append({"RandomStructure": label, "Component": "Residual", "Variance": float(getattr(fit, "scale", np.nan))})

    cov_re = getattr(fit, "cov_re", None)
    if cov_re is not None:
        try:
            if hasattr(cov_re, "index"):
                for i, r in enumerate(cov_re.index):
                    rows.append({
                        "RandomStructure": label,
                        "Component": f"RE Var: {r}",
                        "Variance": float(cov_re.iloc[i, i]),
                    })
            else:
                arr = np.asarray(cov_re)
                for i in range(arr.shape[0]):
                    rows.append({
                        "RandomStructure": label,
                        "Component": f"RE Var idx{i}",
                        "Variance": float(arr[i, i]),
                    })
        except Exception:
            pass

    return pd.DataFrame(rows)


def _main_effect_stability(coef_df: pd.DataFrame) -> pd.DataFrame:
    if coef_df.empty:
        return coef_df
    keep = coef_df[
        coef_df["Term"].str.contains(r"^C\(Complexity\)\[|^C\(WWR\)\[", regex=True, na=False)
        & ~coef_df["Term"].str.contains(":", regex=False)
    ].copy()
    return keep.sort_values(["Term", "RandomStructure"]).reset_index(drop=True)


def _recommend_average_repetition(coef_interactions: pd.DataFrame, round_consistency: pd.DataFrame) -> str:
    # if repetition interactions not significant and consistency high -> recommend averaging
    rep_inter = coef_interactions[coef_interactions["Term"].str.contains(r"C\(Repetition\):", regex=True, na=False)]
    has_sig_rep_inter = bool((rep_inter["p"] < 0.05).any()) if not rep_inter.empty else False

    corr_mean = round_consistency["corr_r1_r2"].mean() if not round_consistency.empty else np.nan
    if (not has_sig_rep_inter) and pd.notna(corr_mean) and corr_mean >= 0.7:
        return "建议可平均 Repetition（Round1/2），用于简化主分析；建议附录保留轮次检验。"
    if has_sig_rep_inter:
        return "不建议平均 Repetition：存在显著轮次交互，需在模型中保留 Repetition。"
    return "暂不建议直接平均 Repetition：请结合轮次交互与一致性指标人工判断。"


def main():
    ap = argparse.ArgumentParser(description="LMM diagnostics (Afford4 main): interaction screening, random-structure sensitivity, repetition diagnostics")
    ap.add_argument("--long-csv", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, default=Path("results/diagnostics"))
    args = ap.parse_args()

    out = args.out_dir
    fig_dir = out / "figures"
    out.mkdir(parents=True, exist_ok=True)
    fig_dir.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(args.long_csv)

    required = ["SubjectID", "S1", "S2", "S3", "S4", "S5", "WWR", "Complexity", "ExperienceGroup", "SportFreqGroup", "Position"]
    miss = [c for c in required if c not in df.columns]
    if miss:
        raise SystemExit(f"Missing required columns: {miss}")

    if "Repetition" not in df.columns:
        df["Repetition"] = df["Block"] if "Block" in df.columns else np.nan

    # Main construct for diagnostics: Afford4 = mean(S1..S4)
    df["Afford4"] = df[["S1", "S2", "S3", "S4"]].mean(axis=1)

    # numeric for random slopes
    df["Complexity_num"] = pd.to_numeric(df["Complexity"], errors="coerce")
    df["WWR_num"] = pd.to_numeric(df["WWR"], errors="coerce")

    keep = ["SubjectID", "Afford4", "WWR", "Complexity", "ExperienceGroup", "SportFreqGroup", "Repetition", "Position", "Complexity_num", "WWR_num"]
    mdf = df.dropna(subset=keep).copy()

    for c in ["WWR", "Complexity", "ExperienceGroup", "SportFreqGroup", "Repetition", "Position"]:
        mdf[c] = mdf[c].astype(str)

    # ------------------------------------------------
    # (1) Interaction screening models
    # ------------------------------------------------
    rhs_base = "C(Complexity) + C(WWR) + C(ExperienceGroup) + C(SportFreqGroup) + C(Repetition) + C(Position)"
    formulas = {
        "A_main": f"Afford4 ~ {rhs_base}",
        "B_add_CxW": f"Afford4 ~ {rhs_base} + C(Complexity):C(WWR)",
        "C_add_RxC": f"Afford4 ~ {rhs_base} + C(Repetition):C(Complexity)",
        "D_add_RxW": f"Afford4 ~ {rhs_base} + C(Repetition):C(WWR)",
    }

    fits = {}
    infos = {}
    coef_tables = []
    for name, formula in formulas.items():
        fit, info = _fit_with_fallback(mdf, formula=formula, re_formula="1 + Complexity_num")
        fits[name] = fit
        infos[name] = info
        if fit is not None:
            coef_tables.append(_extract_coef_table(fit, name))

    model_cmp = pd.DataFrame([
        {
            "Model": k,
            "Formula": formulas[k],
            "AIC": infos[k]["AIC"],
            "BIC": infos[k]["BIC"],
            "LogLik": infos[k]["LogLik"],
            "Converged": infos[k]["converged"],
            "Singular": infos[k].get("singular", False),
            "FitMethod": infos[k]["fit_method"],
            "RandomUsed": infos[k]["re_formula_used"],
            "Warnings": infos[k].get("warnings", ""),
            "Error": infos[k].get("error", ""),
        }
        for k in formulas
    ]).sort_values("AIC", na_position="last").reset_index(drop=True)

    if not model_cmp.empty and pd.notna(model_cmp.loc[0, "AIC"]):
        best_model = model_cmp.loc[0, "Model"]
        best_formula = model_cmp.loc[0, "Formula"]
    else:
        best_model, best_formula = None, None

    base_fit = fits.get("A_main")
    lrt_df = pd.DataFrame([
        _lrt_row("A_main", base_fit, "B_add_CxW", fits.get("B_add_CxW")),
        _lrt_row("A_main", base_fit, "C_add_RxC", fits.get("C_add_RxC")),
        _lrt_row("A_main", base_fit, "D_add_RxW", fits.get("D_add_RxW")),
    ])

    model_cmp["DeltaAIC_vs_best"] = model_cmp["AIC"] - model_cmp["AIC"].min() if model_cmp["AIC"].notna().any() else np.nan
    model_cmp.to_csv(out / "model_comparison_interactions.csv", index=False, encoding="utf-8-sig")
    lrt_df.to_csv(out / "lrt_comparison.csv", index=False, encoding="utf-8-sig")

    coef_all = pd.concat(coef_tables, ignore_index=True) if coef_tables else pd.DataFrame()
    coef_inter = coef_all[coef_all["Term"].str.contains(":", regex=False, na=False)].copy() if not coef_all.empty else pd.DataFrame()
    coef_inter.to_csv(out / "interaction_coefficients.csv", index=False, encoding="utf-8-sig")

    # ------------------------------------------------
    # (2) Random structure sensitivity
    # ------------------------------------------------
    base_formula = formulas["A_main"]
    rs_specs = {
        "RI_only": None,
        "RI_plus_Complexity": "1 + Complexity_num",
        "RI_plus_Complexity_WWR": "1 + Complexity_num + WWR_num",
    }

    rs_fit = {}
    rs_info_rows = []
    rs_coef_rows = []
    rs_var_rows = []

    for label, re_f in rs_specs.items():
        fit, info = _fit_with_fallback(mdf, base_formula, re_formula=re_f)
        rs_fit[label] = fit
        rs_info_rows.append({
            "RandomStructure": label,
            "Requested": re_f if re_f is not None else "1",
            "Converged": info["converged"],
            "Singular": info.get("singular", False),
            "AIC": info["AIC"],
            "BIC": info["BIC"],
            "LogLik": info["LogLik"],
            "FitMethod": info["fit_method"],
            "Warnings": info.get("warnings", ""),
            "Error": info.get("error", ""),
        })

        rs_var_rows.append(_extract_random_variance(fit, label))

        if fit is not None:
            ct = _extract_coef_table(fit, model_name="base")
            ct["RandomStructure"] = label
            rs_coef_rows.append(ct)

    rs_info_df = pd.DataFrame(rs_info_rows)
    rs_info_df.to_csv(out / "random_structure_fit_log.csv", index=False, encoding="utf-8-sig")

    rs_var_df = pd.concat(rs_var_rows, ignore_index=True) if rs_var_rows else pd.DataFrame()
    rs_var_df.to_csv(out / "random_effect_variance.csv", index=False, encoding="utf-8-sig")

    rs_coef_df = pd.concat(rs_coef_rows, ignore_index=True) if rs_coef_rows else pd.DataFrame()
    stability_df = _main_effect_stability(rs_coef_df)
    stability_df.to_csv(out / "main_effect_stability_by_random_structure.csv", index=False, encoding="utf-8-sig")

    # ------------------------------------------------
    # (3) Repetition deep-dive
    # ------------------------------------------------
    # Round means by condition
    round_means = (
        mdf.groupby(["Repetition", "WWR", "Complexity"], dropna=False)["Afford4"]
        .agg(N="count", Mean="mean", SD="std")
        .reset_index()
    )
    round_means.to_csv(out / "round_condition_means.csv", index=False, encoding="utf-8-sig")

    # Subject-level difference distribution (Round2 - Round1)
    piv = mdf.pivot_table(index=["SubjectID", "WWR", "Complexity"], columns="Repetition", values="Afford4", aggfunc="mean").reset_index()
    if "1" in piv.columns and "2" in piv.columns:
        piv["Diff_R2_minus_R1"] = piv["2"] - piv["1"]
    else:
        piv["Diff_R2_minus_R1"] = np.nan
    piv.to_csv(out / "subject_round_diff_distribution.csv", index=False, encoding="utf-8-sig")

    # Extract Repetition×Complexity terms from model C (if available)
    repcx = coef_inter[
        (coef_inter["Model"] == "C_add_RxC")
        & coef_inter["Term"].str.contains(r"C\(Repetition\):C\(Complexity\)|C\(Complexity\):C\(Repetition\)", regex=True, na=False)
    ].copy()
    repcx.to_csv(out / "repetition_complexity_interaction_terms.csv", index=False, encoding="utf-8-sig")

    # ------------------------------------------------
    # (4) plots
    # ------------------------------------------------
    pdat = mdf.copy()

    # Complexity × WWR
    plt.figure(figsize=(7, 4.5))
    sns.pointplot(data=pdat, x="WWR", y="Afford4", hue="Complexity", errorbar="se", dodge=True)
    plt.title("Complexity × WWR on Afford4")
    plt.tight_layout()
    plt.savefig(fig_dir / "interaction_complexity_wwr.png", dpi=220)
    plt.close()

    # Repetition × Complexity
    plt.figure(figsize=(7, 4.5))
    sns.pointplot(data=pdat, x="Repetition", y="Afford4", hue="Complexity", errorbar="se", dodge=True)
    plt.title("Repetition × Complexity on Afford4")
    plt.tight_layout()
    plt.savefig(fig_dir / "interaction_repetition_complexity.png", dpi=220)
    plt.close()

    # Marginal means by key conditions
    plt.figure(figsize=(8, 5))
    sns.pointplot(data=pdat, x="WWR", y="Afford4", hue="Repetition", errorbar="se", dodge=True)
    plt.title("Marginal Means: WWR by Repetition")
    plt.tight_layout()
    plt.savefig(fig_dir / "marginal_means_wwr_repetition.png", dpi=220)
    plt.close()

    # ------------------------------------------------
    # (5) markdown report
    # ------------------------------------------------
    rec_avg_rep = _recommend_average_repetition(coef_inter, pd.DataFrame({
        "corr_r1_r2": [piv["1"].corr(piv["2"]) if ("1" in piv.columns and "2" in piv.columns) else np.nan]
    }))

    rep_inter_sig = repcx[repcx["p"] < 0.05] if not repcx.empty else pd.DataFrame()
    main_sig = coef_all[(~coef_all["Term"].str.contains(":", regex=False)) & (coef_all["Model"] == (best_model or "A_main")) & (coef_all["p"] < 0.05)] if not coef_all.empty else pd.DataFrame()

    lines = [
        "# analysis_report",
        "",
        "## 1) 模型对比总结",
        f"- 候选模型：A(main), B(+Complexity×WWR), C(+Repetition×Complexity), D(+Repetition×WWR)",
        f"- 最优模型（按AIC）：{best_model if best_model else 'N/A'}",
        f"- 最优公式：`{best_formula if best_formula else 'N/A'}`",
        "",
        "### ΔAIC / BIC",
        model_cmp.to_markdown(index=False) if not model_cmp.empty else "(no model comparison available)",
        "",
        "### LRT（相对A_main）",
        lrt_df.to_markdown(index=False) if not lrt_df.empty else "(no lrt available)",
        "",
        "## 2) 主效应结论（最优/基准模型）",
    ]

    if main_sig.empty:
        lines.append("- 主效应未见显著项（p<.05）。")
    else:
        for _, r in main_sig.sort_values("p").iterrows():
            lines.append(f"- {r['Term']}: β={r['Coef']:.3f}, SE={r['SE']:.3f}, z={r['z']:.3f}, p={r['p']:.4f}{r['Sig']}")

    lines.extend([
        "",
        "## 3) 交互结论",
    ])
    if coef_inter.empty:
        lines.append("- 无可用交互系数输出。")
    else:
        sig_inter = coef_inter[coef_inter["p"] < 0.05]
        if sig_inter.empty:
            lines.append("- 交互项整体未达显著（p<.05）。")
        else:
            for _, r in sig_inter.sort_values("p").head(10).iterrows():
                lines.append(f"- [{r['Model']}] {r['Term']}: β={r['Coef']:.3f}, p={r['p']:.4f}{r['Sig']}")

    lines.extend([
        "",
        "## 4) 稳健性结论（随机结构敏感性）",
        rs_info_df.to_markdown(index=False) if not rs_info_df.empty else "(no random-structure fit log)",
        "",
        "主效应稳定性（Complexity/WWR）：",
        stability_df.to_markdown(index=False) if not stability_df.empty else "(no stability table)",
        "",
        "## 5) Repetition 结论",
        "Round 条件均值：",
        round_means.to_markdown(index=False) if not round_means.empty else "(no round means)",
        "",
        f"Repetition×Complexity 显著项数量：{0 if repcx.empty else int((repcx['p'] < 0.05).sum())}",
        f"是否建议平均 Repetition：{rec_avg_rep}",
        "",
        "## 6) 输出文件",
        "- model_comparison_interactions.csv",
        "- lrt_comparison.csv",
        "- interaction_coefficients.csv",
        "- random_structure_fit_log.csv",
        "- random_effect_variance.csv",
        "- main_effect_stability_by_random_structure.csv",
        "- round_condition_means.csv",
        "- subject_round_diff_distribution.csv",
        "- repetition_complexity_interaction_terms.csv",
        "- figures/*.png",
    ])

    (out / "analysis_report.md").write_text("\n".join(lines), encoding="utf-8")

    summary = {
        "best_model_by_aic": best_model,
        "best_formula": best_formula,
        "outputs": [
            "analysis_report.md",
            "model_comparison_interactions.csv",
            "lrt_comparison.csv",
            "interaction_coefficients.csv",
            "random_structure_fit_log.csv",
            "random_effect_variance.csv",
            "main_effect_stability_by_random_structure.csv",
            "round_condition_means.csv",
            "subject_round_diff_distribution.csv",
            "repetition_complexity_interaction_terms.csv",
            "figures/interaction_complexity_wwr.png",
            "figures/interaction_repetition_complexity.png",
            "figures/marginal_means_wwr_repetition.png",
        ],
    }
    (out / "diagnostics_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
