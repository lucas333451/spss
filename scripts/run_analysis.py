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

from plot_style import apply_bae_style


def cronbach_alpha(df: pd.DataFrame) -> float:
    x = df.dropna()
    if x.shape[0] < 3 or x.shape[1] < 2:
        return np.nan
    return float(pg.cronbach_alpha(data=x)[0])


def _rescale_9_to_7(x):
    if pd.isna(x):
        return np.nan
    return 1.0 + (float(x) - 1.0) * (6.0 / 8.0)


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
        if any(x in term for x in ["C(WWR)", "C(Complexity)", "C(ExperienceGroup)"]):
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
    }
    if t in mapping:
        return mapping[t]

    t = t.replace("C(ExperienceGroup)[T.", "Experience group: ")
    t = t.replace('C(WWR)[T.', 'WWR: ')
    t = t.replace('C(Complexity)[T.', 'Complexity: ')
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


def _extract_random_effects_summary(fit) -> pd.DataFrame:
    if fit is None:
        return pd.DataFrame()

    rows = []
    cov_re = getattr(fit, "cov_re", None)
    if cov_re is not None:
        try:
            cov = np.asarray(cov_re, dtype=float)
            names = list(getattr(cov_re, "index", []))
            if not names:
                names = [f"RE{i+1}" for i in range(cov.shape[0])]

            for i, nm in enumerate(names):
                v = float(cov[i, i])
                rows.append({"Component": nm, "Type": "Var", "Value": v})
                rows.append({"Component": nm, "Type": "SD", "Value": float(np.sqrt(v)) if v >= 0 else np.nan})

            for i in range(len(names)):
                for j in range(i + 1, len(names)):
                    denom = np.sqrt(cov[i, i] * cov[j, j])
                    corr = float(cov[i, j] / denom) if denom and np.isfinite(denom) and denom > 0 else np.nan
                    rows.append({"Component": f"{names[i]}~{names[j]}", "Type": "Corr", "Value": corr})
        except Exception:
            pass

    try:
        res_var = float(getattr(fit, "scale", np.nan))
        if np.isfinite(res_var):
            rows.append({"Component": "Residual", "Type": "Var", "Value": res_var})
            rows.append({"Component": "Residual", "Type": "SD", "Value": float(np.sqrt(res_var)) if res_var >= 0 else np.nan})
    except Exception:
        pass

    out = pd.DataFrame(rows)
    if out.empty:
        return out
    wide = out.pivot_table(index="Component", columns="Type", values="Value", aggfunc="first").reset_index()
    cols = [c for c in ["Component", "Var", "SD", "Corr"] if c in wide.columns]
    return wide[cols]


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
            with warnings.catch_warnings(record=True) as wlist:
                warnings.simplefilter("always")
                mdl = mixedlm(formula=formula, data=data, groups=data["SubjectID"], re_formula=a["re_formula"])
                fit = mdl.fit(reml=False, method=a["method"], maxiter=2000)
            warn_msgs = [str(w.message) for w in wlist]
            boundary = any("boundary of the parameter space" in m for m in warn_msgs)
            hessian_pd = not any("Hessian matrix" in m and "not positive definite" in m for m in warn_msgs)
            info = {
                "method": a["method"],
                "re_formula_requested": re_formula,
                "re_formula_used": a["re_formula"],
                "fallback_used": bool(a["re_formula"] != re_formula),
                "converged": bool(getattr(fit, "converged", True)),
                "aic": float(fit.aic) if pd.notna(fit.aic) else np.nan,
                "bic": float(fit.bic) if pd.notna(fit.bic) else np.nan,
                "llf": float(fit.llf) if pd.notna(fit.llf) else np.nan,
                "boundary_warning": boundary,
                "hessian_not_pd": not hessian_pd,
                "warnings": " | ".join(dict.fromkeys(warn_msgs)),
            }
            if boundary or not hessian_pd:
                last_err = info["warnings"] or "fit_quality_warning"
                continue
            return fit, info
        except Exception as e:
            last_err = str(e)
    raise RuntimeError(f"MixedLM failed. formula={formula}, last_error={last_err}")


def _build_model_comparison(model_df: pd.DataFrame, dv_col: str):
    f_a = f"{dv_col} ~ C(WWR) + C(Complexity) + C(ExperienceGroup)"
    f_b = f"{dv_col} ~ C(WWR) * C(Complexity) + C(ExperienceGroup)"
    f_c = f"{dv_col} ~ C(WWR) * C(Complexity) * C(ExperienceGroup)"

    specs = [
        ("Model_A_compact", f_a),
        ("Model_B_two_way", f_b),
        ("Model_C_three_way", f_c),
    ]

    rows, fits = [], {}
    primary_name, primary_formula = specs[0]
    primary_error = None

    for name, formula in specs:
        try:
            fit, info = _fit_with_fallback(model_df, formula, re_formula="1 + C(Complexity)")
            fits[name] = {"fit": fit, "formula": formula, "info": info, "status": "ok"}
            rows.append({
                "Model": name,
                "Formula": formula,
                "AIC": info["aic"],
                "BIC": info["bic"],
                "LogLik": info["llf"],
                "Converged": info["converged"],
                "FitMethod": info["method"],
                "RandomStructureUsed": info["re_formula_used"] if info["re_formula_used"] is not None else "1",
                "Status": "ok",
                "Error": "",
            })
        except Exception as e:
            err = str(e)
            fits[name] = {"fit": None, "formula": formula, "info": None, "status": "failed", "error": err}
            rows.append({
                "Model": name,
                "Formula": formula,
                "AIC": np.nan,
                "BIC": np.nan,
                "LogLik": np.nan,
                "Converged": False,
                "FitMethod": "failed",
                "RandomStructureUsed": "NA",
                "Status": "failed",
                "Error": err,
            })
            if name == primary_name:
                primary_error = err

    cmp_df = pd.DataFrame(rows)
    ok_cmp = cmp_df.loc[cmp_df["Status"] == "ok"].copy()
    if ok_cmp.empty or fits.get(primary_name, {}).get("fit") is None:
        raise RuntimeError(
            f"Primary compact model failed; cannot continue significance analysis. primary_formula={primary_formula}, error={primary_error or 'no successful fits'}"
        )

    ok_cmp = ok_cmp.sort_values("AIC").reset_index(drop=True)
    recommended_name = str(ok_cmp.iloc[0]["Model"])
    best = {
        "primary_model": primary_name,
        "primary_formula": primary_formula,
        "recommended_model_by_aic": recommended_name,
        "recommended_formula_by_aic": fits[recommended_name]["formula"],
        "fit": fits[primary_name]["fit"],
        "info": fits[primary_name]["info"],
        "fit_method": fits[primary_name]["info"]["method"],
        "random_structure_used": fits[primary_name]["info"]["re_formula_used"] if fits[primary_name]["info"]["re_formula_used"] is not None else "1",
    }
    cmp_df = cmp_df.sort_values(["Status", "AIC"], na_position="last").reset_index(drop=True)
    return cmp_df, best, fits


def _build_paper_tables(model_df: pd.DataFrame, coef_df: pd.DataFrame, dv_col: str, random_df: pd.DataFrame | None = None):
    d = model_df.copy()
    desc = d.groupby(["WWR", "Complexity"], as_index=False)[dv_col].agg(n="count", mean="mean", sd="std")

    fixed = coef_df.copy()
    fixed["EffectType"], fixed["EffectRaw"] = zip(*fixed["Term"].map(_classify_effect))
    fixed["APA_Term"] = fixed["Term"].map(_humanize_term)

    infer = fixed[fixed["EffectType"].str.contains("Main Effect|Interaction", na=False)].copy()
    infer = infer[["EffectType", "APA_Term", "Coef", "SE", "z", "p", "Sig", "CI95_low", "CI95_high"]]
    rand = random_df.copy() if random_df is not None else pd.DataFrame()
    return desc, fixed, infer, rand


def _simple_effects_by_wwr(model_df: pd.DataFrame, dv_col: str) -> pd.DataFrame:
    rows = []
    for wwr, sub in model_df.groupby("WWR"):
        wide = sub.pivot_table(index="SubjectID", columns="Complexity", values=dv_col, aggfunc="mean")
        if "0" not in wide.columns or "1" not in wide.columns:
            continue
        a = pd.to_numeric(wide["0"], errors="coerce")
        b = pd.to_numeric(wide["1"], errors="coerce")
        valid = a.notna() & b.notna()
        a2 = a[valid].to_numpy(dtype=float)
        b2 = b[valid].to_numpy(dtype=float)
        if len(a2) < 3:
            continue
        t_res = ttest_rel(b2, a2, nan_policy="omit")
        diff = b2 - a2
        dz = float(np.mean(diff) / np.std(diff, ddof=1)) if len(diff) >= 2 and np.std(diff, ddof=1) > 0 else np.nan
        rows.append({
            "WWR": wwr,
            "n": int(len(diff)),
            "Mean_C0": float(np.mean(a2)),
            "Mean_C1": float(np.mean(b2)),
            "Diff_C1_minus_C0": float(np.mean(diff)),
            "t": float(t_res.statistic) if pd.notna(t_res.statistic) else np.nan,
            "p": float(t_res.pvalue) if pd.notna(t_res.pvalue) else np.nan,
            "dz": dz,
        })
    out = pd.DataFrame(rows)
    if not out.empty:
        mask = out["p"].notna()
        if mask.any():
            out.loc[mask, "p_holm"] = multipletests(out.loc[mask, "p"], method="holm")[1]
        else:
            out["p_holm"] = np.nan
    return out


def _auto_results_draft_zh(best: dict, infer_df: pd.DataFrame, simple_df: pd.DataFrame) -> str:
    lines = []
    lines.append("# 结果草稿（中文自动生成）")
    lines.append("")
    lines.append(f"主报告模型固定为：{best['primary_model']}")
    lines.append(f"公式：{best['primary_formula']}")
    lines.append("")
    if not infer_df.empty:
        sig = infer_df[infer_df["p"] < 0.05].copy()
        if not sig.empty:
            lines.append("## 显著项（p < 0.05）")
            for _, r in sig.iterrows():
                lines.append(f"- {r['EffectType']}：{r['APA_Term']}，Coef={r['Coef']:.3f}, z={r['z']:.3f}, p={r['p']:.4f}")
    if not simple_df.empty:
        lines.append("")
        lines.append("## Complexity 在各 WWR 下的简单效应")
        for _, r in simple_df.iterrows():
            lines.append(f"- WWR={r['WWR']}：C1-C0={r['Diff_C1_minus_C0']:.3f}, p={r['p']:.4f}, p_holm={r.get('p_holm', np.nan):.4f}")
    return "\n".join(lines)


def _fmt(v, nd=3):
    if v is None or pd.isna(v):
        return "NA"
    return f"{float(v):.{nd}f}"


def _summary_box(ax, title: str, lines: list[str]):
    ax.axis("off")
    ax.set_facecolor("#F7FAF8")
    ax.text(0.03, 0.97, title, va="top", ha="left", fontsize=10.2, fontweight="bold", color="#40534C")
    ax.text(
        0.03, 0.90, "\n".join(lines), va="top", ha="left", fontsize=8.6, color="#50615A", linespacing=1.35,
        bbox=dict(boxstyle="round,pad=0.45", fc="#F4F8F6", ec="#D5DFD9", lw=0.8)
    )


def _plot_model_comparison(cmp_df: pd.DataFrame, out_dir: Path) -> str | None:
    if cmp_df.empty:
        return None
    fig = plt.figure(figsize=(9.4, 4.8))
    gs = fig.add_gridspec(1, 2, width_ratios=[3.4, 1.5], wspace=0.16)
    ax = fig.add_subplot(gs[0, 0])
    ax2 = fig.add_subplot(gs[0, 1])
    x = cmp_df.copy().sort_values("AIC", ascending=True)
    sns.barplot(data=x, y="Model", x="AIC", color="#A9D6CB", ax=ax)
    ax.set_title("Model comparison by AIC")
    ax.set_xlabel("AIC")
    ax.set_ylabel("")
    best_row = x.iloc[0]
    _summary_box(ax2, "Model summary", [
        f"Best by AIC: {best_row['Model']}",
        f"AIC={_fmt(best_row['AIC'])}",
        f"BIC={_fmt(best_row['BIC'])}",
        f"LogLik={_fmt(best_row['LogLik'])}",
    ])
    out_dir.mkdir(parents=True, exist_ok=True)
    p = out_dir / "model_comparison_aic.png"
    fig.savefig(p, dpi=230)
    plt.close(fig)
    return str(p)


def _plot_fixed_effects(fixed_df: pd.DataFrame, out_dir: Path) -> str | None:
    if fixed_df.empty:
        return None
    x = fixed_df[fixed_df["Term"] != "Intercept"].copy()
    if x.empty:
        return None
    x = x.sort_values("Coef")
    fig = plt.figure(figsize=(10.5, max(4.8, 0.34 * len(x) + 1.6)))
    gs = fig.add_gridspec(1, 2, width_ratios=[3.6, 1.4], wspace=0.12)
    ax = fig.add_subplot(gs[0, 0])
    ax2 = fig.add_subplot(gs[0, 1])
    ax.axvline(0, color="#70817A", lw=1)
    ax.errorbar(x["Coef"], np.arange(len(x)), xerr=[x["Coef"] - x["CI95_low"], x["CI95_high"] - x["Coef"]], fmt='o', color="#6FAF9F", ecolor="#A8D5C8", capsize=2)
    ax.set_yticks(np.arange(len(x)))
    ax.set_yticklabels([_humanize_term(t) for t in x["Term"]], fontsize=8)
    ax.set_title("Fixed effects with 95% CI")
    ax.set_xlabel("Coefficient")
    sig_n = int((x["p"] < 0.05).sum())
    _summary_box(ax2, "Fixed effects", [
        f"Terms shown: {len(x)}",
        f"Significant (p<0.05): {sig_n}",
        f"Strongest +Coef: {_humanize_term(str(x.iloc[-1]['Term']))}",
        f"Strongest -Coef: {_humanize_term(str(x.iloc[0]['Term']))}",
    ])
    out_dir.mkdir(parents=True, exist_ok=True)
    p = out_dir / "fixed_effects_forest.png"
    fig.savefig(p, dpi=230)
    plt.close(fig)
    return str(p)


def _plot_interactions(infer_df: pd.DataFrame, out_dir: Path) -> str | None:
    if infer_df.empty:
        return None
    x = infer_df.copy()
    x["minuslog10p"] = -np.log10(pd.to_numeric(x["p"], errors="coerce"))
    x = x.sort_values("minuslog10p", ascending=True)
    fig = plt.figure(figsize=(10.2, max(4.8, 0.34 * len(x) + 1.4)))
    gs = fig.add_gridspec(1, 2, width_ratios=[3.6, 1.4], wspace=0.12)
    ax = fig.add_subplot(gs[0, 0])
    ax2 = fig.add_subplot(gs[0, 1])
    palette = x["EffectType"].map({"Main Effect": "#6FAF9F", "Interaction (2-way)": "#8FA3B8", "Interaction (3-way)": "#C8B98B"}).fillna("#A8C7CF")
    ax.barh(np.arange(len(x)), x["minuslog10p"], color=list(palette))
    ax.set_yticks(np.arange(len(x)))
    ax.set_yticklabels(x["APA_Term"], fontsize=8)
    ax.set_xlabel("-log10(p)")
    ax.set_title("Main and interaction effects")
    _summary_box(ax2, "Interaction summary", [
        f"Rows: {len(x)}",
        f"Main effects: {int((x['EffectType'] == 'Main Effect').sum())}",
        f"2-way: {int((x['EffectType'] == 'Interaction (2-way)').sum())}",
        f"3-way+: {int(x['EffectType'].str.contains('3-way|4-way', na=False).sum())}",
    ])
    out_dir.mkdir(parents=True, exist_ok=True)
    p = out_dir / "main_interactions_summary.png"
    fig.savefig(p, dpi=230)
    plt.close(fig)
    return str(p)


def _plot_random_effects(rand_df: pd.DataFrame, out_dir: Path) -> str | None:
    if rand_df is None or rand_df.empty:
        return None
    x = rand_df.copy()
    value_cols = [c for c in ["Var", "SD", "Corr"] if c in x.columns]
    if not value_cols:
        return None

    long = x.melt(id_vars=["Component"], value_vars=value_cols, var_name="Metric", value_name="Value").dropna(subset=["Value"])
    if long.empty:
        return None

    fig = plt.figure(figsize=(10.0, max(4.8, 0.35 * len(long) + 1.4)))
    gs = fig.add_gridspec(1, 2, width_ratios=[3.5, 1.5], wspace=0.12)
    ax = fig.add_subplot(gs[0, 0])
    ax2 = fig.add_subplot(gs[0, 1])

    long["Label"] = long["Component"].astype(str) + " | " + long["Metric"].astype(str)
    long = long.sort_values("Value")
    palette = long["Metric"].map({"Var": "#A9D6CB", "SD": "#8FA3B8", "Corr": "#C8B98B"}).fillna("#A8C7CF")
    ax.barh(np.arange(len(long)), long["Value"], color=list(palette))
    ax.axvline(0, color="#70817A", lw=1)
    ax.set_yticks(np.arange(len(long)))
    ax.set_yticklabels(long["Label"], fontsize=8)
    ax.set_title("Random effects summary")
    ax.set_xlabel("Value")

    _summary_box(ax2, "Random effects", [
        f"Components: {x['Component'].nunique()}",
        f"Metrics shown: {', '.join(value_cols)}",
        f"Residual Var: {_fmt(x.loc[x['Component'] == 'Residual', 'Var'].iloc[0]) if ('Residual' in x['Component'].values and 'Var' in x.columns) else 'NA'}",
    ])
    out_dir.mkdir(parents=True, exist_ok=True)
    p = out_dir / "random_effects_summary.png"
    fig.savefig(p, dpi=230)
    plt.close(fig)
    return str(p)


def _plot_simple_effects(simple_df: pd.DataFrame, out_dir: Path) -> str | None:
    if simple_df.empty:
        return None
    x = simple_df.copy().sort_values("WWR")
    fig = plt.figure(figsize=(9.2, 4.8))
    gs = fig.add_gridspec(1, 2, width_ratios=[3.2, 1.5], wspace=0.12)
    ax = fig.add_subplot(gs[0, 0])
    ax2 = fig.add_subplot(gs[0, 1])
    bars = ax.bar(x["WWR"].astype(str), x["Diff_C1_minus_C0"], color="#8EC5B6")
    ax.axhline(0, color="#70817A", lw=1)
    ax.set_title("Simple effects: C1 - C0 within each WWR")
    ax.set_xlabel("WWR")
    ax.set_ylabel("Mean difference")
    for b, p in zip(bars, x["p"]):
        ax.text(b.get_x() + b.get_width()/2, b.get_height(), f"p={_fmt(p, 3)}", ha="center", va="bottom", fontsize=8, color="#50615A")
    best = x.loc[x["p"].idxmin()] if x["p"].notna().any() else x.iloc[0]
    _summary_box(ax2, "Simple-effects summary", [
        f"Most evidence at WWR={best['WWR']}",
        f"C1-C0={_fmt(best['Diff_C1_minus_C0'])}",
        f"p={_fmt(best['p'])}",
        f"Holm p={_fmt(best.get('p_holm', np.nan))}",
        f"dz={_fmt(best.get('dz', np.nan))}",
    ])
    out_dir.mkdir(parents=True, exist_ok=True)
    p = out_dir / "simple_effects_complexity_by_wwr.png"
    fig.savefig(p, dpi=230)
    plt.close(fig)
    return str(p)


def main():
    ap = argparse.ArgumentParser(description="Run LMM on long-format questionnaire data and export paper-ready tables")
    ap.add_argument("--long-csv", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, default=Path("results/model"))
    ap.add_argument("--afford4-min-items", type=int, default=3, help="Minimum valid items among S1-S4 required to compute Afford4 (default: 3)")
    ap.add_argument("--exclude-subjects", default="", help="Comma-separated SubjectID list for exclusion (used by qc branch in clean main pipeline)")
    args = ap.parse_args()

    apply_bae_style()

    out = args.out_dir
    out.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(args.long_csv)
    if args.exclude_subjects and "SubjectID" in df.columns:
        names = [x.strip() for x in str(args.exclude_subjects).split(",") if x.strip()]
        sid = df["SubjectID"].astype(str).str.strip()
        df = df.loc[~sid.isin(set(names))].copy()

    afford_min_items = int(args.afford4_min_items)
    df["Afford4_n_valid"] = df[["S1", "S2", "S3", "S4"]].notna().sum(axis=1).astype(int)
    df["Afford4_lenient"] = df[["S1", "S2", "S3", "S4"]].mean(axis=1, skipna=True)
    df["Afford4"] = df["Afford4_lenient"].where(df["Afford4_n_valid"] >= afford_min_items, np.nan)

    dv_col = "Afford4"
    if dv_col not in df.columns:
        raise SystemExit("Missing S1-S4 columns required to build Afford4.")

    alpha = cronbach_alpha(df[["S1", "S2", "S3", "S4"]])

    if "ExperienceGroup" not in df.columns:
        raise SystemExit("Missing ExperienceGroup in long CSV. Please re-run transform_wide_to_long.py with latest version.")
    if "SAM_Valence" not in df.columns and "S5" in df.columns:
        df["SAM_Valence"] = df["S5"]
    keep_cols = ["SubjectID", dv_col, "WWR", "Complexity", "ExperienceGroup"]
    model_df = df.dropna(subset=keep_cols).copy()

    for c in ["WWR", "Complexity", "ExperienceGroup"]:
        model_df[c] = model_df[c].astype(str)

    cmp_df, best, fitted_models = _build_model_comparison(model_df, dv_col=dv_col)
    fit = best["fit"]
    fit_info = best["info"]

    coef_df = _extract_coef_table(fit)
    rand_df = _extract_random_effects_summary(fit)
    desc_df, fixed_df, infer_df, rand_df = _build_paper_tables(model_df, coef_df, dv_col=dv_col, random_df=rand_df)
    simple_df = _simple_effects_by_wwr(model_df, dv_col=dv_col)

    sens_out = None
    try:
        model_df_lenient = df.dropna(subset=["Afford4_lenient", "WWR", "Complexity", "ExperienceGroup"]).copy()
        cmp_lenient, best_lenient, _ = _build_model_comparison(model_df_lenient, dv_col="Afford4_lenient")
        fit_lenient = best_lenient["fit"]
        coef_primary = _extract_coef_table(fit)
        coef_lenient = _extract_coef_table(fit_lenient)
        m = coef_primary[["Term","Coef","SE","z","p"]].merge(
            coef_lenient[["Term","Coef","SE","z","p"]], on="Term", how="outer", suffixes=("_primary","_lenient")
        )
        m["delta_coef"] = m["Coef_lenient"] - m["Coef_primary"]
        m["delta_p"] = m["p_lenient"] - m["p_primary"]
        m["afford4_min_items"] = afford_min_items
        sens_out = m
    except Exception:
        sens_out = None

    csv_dir = out / "csv"
    png_dir = out / "png"
    md_dir = out / "md"
    txt_dir = out / "txt"
    json_dir = out / "json"
    for d in [csv_dir, png_dir, md_dir, txt_dir, json_dir]:
        d.mkdir(parents=True, exist_ok=True)

    plt.figure(figsize=(9, 5))
    pdat = model_df.copy()
    pdat["Complexity"] = pdat["Complexity"].replace({"0": "C0", "1": "C1"})
    sns.pointplot(data=pdat, x="WWR", y=dv_col, hue="Complexity", errorbar="se", dodge=True)
    plt.title(f"WWR × Complexity on {dv_col}")
    plt.tight_layout()
    plt.savefig(png_dir / "wwr_complexity_afford4.png", dpi=220)
    plt.close()

    (txt_dir / "lmm_summary.txt").write_text(str(fit.summary()), encoding="utf-8")
    (txt_dir / "model_formula.txt").write_text(str(best["primary_formula"]), encoding="utf-8")
    (txt_dir / "model_formula_recommended_by_aic.txt").write_text(str(best["recommended_formula_by_aic"]), encoding="utf-8")
    cmp_df.to_csv(csv_dir / "model_comparison.csv", index=False, encoding="utf-8-sig")
    desc_df.to_csv(csv_dir / "table_descriptives.csv", index=False, encoding="utf-8-sig")
    fixed_df.to_csv(csv_dir / "table_fixed_effects.csv", index=False, encoding="utf-8-sig")
    infer_df.to_csv(csv_dir / "table_main_interactions.csv", index=False, encoding="utf-8-sig")
    if rand_df is not None and not rand_df.empty:
        rand_df.to_csv(csv_dir / "table_random_effects.csv", index=False, encoding="utf-8-sig")
    simple_df.to_csv(csv_dir / "table_simple_effects_complexity_by_wwr.csv", index=False, encoding="utf-8-sig")
    if sens_out is not None:
        sens_out.to_csv(csv_dir / "afford4_missing_sensitivity.csv", index=False, encoding="utf-8-sig")

    fig_dir = png_dir
    fig_paths = {
        "figure_wwr_complexity": str(out / "figures" / "wwr_complexity_afford4.png"),
        "figure_model_comparison": _plot_model_comparison(cmp_df, fig_dir),
        "figure_fixed_effects": _plot_fixed_effects(fixed_df, fig_dir),
        "figure_interactions": _plot_interactions(infer_df, fig_dir),
        "figure_random_effects": _plot_random_effects(rand_df, fig_dir),
        "figure_simple_effects": _plot_simple_effects(simple_df, fig_dir),
    }

    md_lines = [
        "# Paper-ready Results Tables",
        "",
        "Scale note: S1~S4 are 7-point and define the main construct (`Afford4`). S5 is 9-point and reported as supplementary emotional-experience item (not merged).",
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
        "## Table 3. Random effects (variance components)",
        _to_markdown_table(rand_df) if (rand_df is not None and not rand_df.empty) else "(Not available for this fit)",
        "",
        "## Table 4. Main and interaction effects (compact)",
        _to_markdown_table(infer_df),
        "",
        "## Table 5. Simple effects: Complexity (C1 vs C0) within each WWR",
        _to_markdown_table(simple_df) if not simple_df.empty else "No analyzable simple-effects rows.",
        "",
        f"Reliability (Cronbach's alpha, S1-S4): {alpha:.3f}" if not np.isnan(alpha) else "Reliability: NA",
        "",
        f"Primary model (pre-registered style): {best['primary_model']}",
        f"Formula (primary): {best['primary_formula']}",
        f"Recommended by AIC (exploratory/sensitivity): {best['recommended_model_by_aic']}",
        f"Formula (AIC-best): {best['recommended_formula_by_aic']}",
        f"Random structure used: {best['random_structure_used']}",
    ]
    (md_dir / "paper_tables.md").write_text("\n".join(md_lines), encoding="utf-8")

    draft_zh = _auto_results_draft_zh(best, infer_df, simple_df)
    (md_dir / "results_draft_zh.md").write_text(draft_zh, encoding="utf-8")

    report = {
        "n_rows_input": int(len(df)),
        "n_rows_model": int(len(model_df)),
        "n_subjects": int(model_df["SubjectID"].nunique()),
        "cronbach_alpha_s1_s4": None if np.isnan(alpha) else float(alpha),
        "dv_used": dv_col,
        "modeling_note": "Primary model is fixed to the 3-factor questionnaire core model (WWR, Complexity, ExperienceGroup); interaction extensions are reported as exploratory/sensitivity.",
        "primary_model": best["primary_model"],
        "primary_formula": best["primary_formula"],
        "recommended_model_by_aic": best["recommended_model_by_aic"],
        "recommended_formula_by_aic": best["recommended_formula_by_aic"],
        "random_structure_requested": "(1 + Complexity | Subject)",
        "random_structure_used": best["random_structure_used"],
        "fit_method": best["fit_method"],
        "fit_fallback_to_random_intercept": bool(fit_info.get("fallback_used", False)),
        "outputs": {
            "model_comparison_csv": str(csv_dir / "model_comparison.csv"),
            "table_descriptives_csv": str(csv_dir / "table_descriptives.csv"),
            "table_fixed_effects_csv": str(csv_dir / "table_fixed_effects.csv"),
            "table_main_interactions_csv": str(csv_dir / "table_main_interactions.csv"),
            "table_simple_effects_csv": str(csv_dir / "table_simple_effects_complexity_by_wwr.csv"),
            "table_random_effects_csv": str(csv_dir / "table_random_effects.csv") if (rand_df is not None and not rand_df.empty) else None,
            "afford4_missing_sensitivity_csv": str(csv_dir / "afford4_missing_sensitivity.csv") if (sens_out is not None) else None,
            "paper_tables_md": str(md_dir / "paper_tables.md"),
            "results_draft_zh_md": str(md_dir / "results_draft_zh.md"),
            **fig_paths,
        },
    }
    (json_dir / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
