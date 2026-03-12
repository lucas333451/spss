#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import argparse
import json

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from statsmodels.formula.api import mixedlm

from plot_style import apply_bae_style

S_COLS = ["S1", "S2", "S3", "S4", "S5"]
B_COLS = ["B1", "B2", "B3"]
IPQ_COLS = ["IPQ1", "IPQ2", "IPQ3", "IPQ4", "IPQ5", "IPQ6"]


def _exclude_subjects(df: pd.DataFrame, text: str) -> pd.DataFrame:
    if not text or "SubjectID" not in df.columns:
        return df
    names = [x.strip() for x in str(text).split(",") if x.strip()]
    if not names:
        return df
    sid = df["SubjectID"].astype(str).str.strip()
    return df.loc[~sid.isin(set(names))].copy()


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


def _fmt(v, nd=3):
    if v is None or pd.isna(v):
        return "NA"
    return f"{float(v):.{nd}f}"


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


def _classify_effect(term: str) -> str:
    if term == "Intercept":
        return "Control"
    n_int = term.count(":")
    if n_int == 0:
        if any(x in term for x in ["C(WWR)", "C(Complexity)", "C(ExperienceGroup)"]):
            return "Main Effect"
        return "Control"
    if n_int == 1:
        return "Interaction (2-way)"
    if n_int == 2:
        return "Interaction (3-way)"
    return "Interaction (4-way+)"


def _fit_with_fallback(data: pd.DataFrame, formula: str, re_formula: str | None):
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
    raise RuntimeError(f"MixedLM failed. formula={formula}, last_error={last_err}")


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
        rows.append({
            "Term": term,
            "Coef": params[term],
            "SE": bse[term],
            "z": zvals[term],
            "p": pvals[term],
            "CI95_low": ci.loc[term, 0] if term in ci.index else np.nan,
            "CI95_high": ci.loc[term, 1] if term in ci.index else np.nan,
        })
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    out["Sig"] = out["p"].map(_sigstar)
    out["EffectType"] = out["Term"].map(_classify_effect)
    out["APA_Term"] = out["Term"].map(_humanize_term)
    return out


def _model_specs(domain: str, dv: str) -> tuple[list[tuple[str, str]], str | None, str]:
    if domain == "b_items":
        specs = [
            ("Model_A_compact", f"{dv} ~ C(WWR) + C(ExperienceGroup)"),
            ("Model_B_interaction", f"{dv} ~ C(WWR) * C(ExperienceGroup)"),
        ]
        return specs, None, "B items are analyzed on Complexity=1 subset by design; Complexity is therefore not modeled again."
    specs = [
        ("Model_A_compact", f"{dv} ~ C(WWR) + C(Complexity) + C(ExperienceGroup)"),
        ("Model_B_key_interaction", f"{dv} ~ C(WWR) * C(Complexity) + C(ExperienceGroup)"),
        ("Model_C_three_way", f"{dv} ~ C(WWR) * C(Complexity) * C(ExperienceGroup)"),
    ]
    return specs, "1 + C(Complexity)", "Full 3-factor item-level model."


def _prepare_domain_df(df: pd.DataFrame, domain: str, dv: str) -> pd.DataFrame:
    x = df.copy()
    if domain == "b_items":
        x = x[pd.to_numeric(x["Complexity"], errors="coerce") == 1].copy()
        keep_cols = ["SubjectID", dv, "WWR", "ExperienceGroup"]
        x = x.dropna(subset=keep_cols).copy()
        for c in ["WWR", "ExperienceGroup"]:
            x[c] = x[c].astype(str)
        return x
    keep_cols = ["SubjectID", dv, "WWR", "Complexity", "ExperienceGroup"]
    x = x.dropna(subset=keep_cols).copy()
    for c in ["WWR", "Complexity", "ExperienceGroup"]:
        x[c] = x[c].astype(str)
    return x


def _run_one_dv(df: pd.DataFrame, domain: str, dv: str) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    model_df = _prepare_domain_df(df, domain, dv)
    specs, re_formula, note = _model_specs(domain, dv)
    rows = []
    fits = {}
    primary_name, primary_formula = specs[0]
    primary_error = None

    for name, formula in specs:
        try:
            fit, info = _fit_with_fallback(model_df, formula=formula, re_formula=re_formula)
            fits[name] = {"fit": fit, "info": info, "formula": formula, "status": "ok"}
            rows.append({
                "DV": dv,
                "Domain": domain,
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
                "n_rows": int(len(model_df)),
                "n_subjects": int(model_df["SubjectID"].nunique()),
                "DesignNote": note,
            })
        except Exception as e:
            err = str(e)
            fits[name] = {"fit": None, "info": None, "formula": formula, "status": "failed", "error": err}
            rows.append({
                "DV": dv,
                "Domain": domain,
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
                "n_rows": int(len(model_df)),
                "n_subjects": int(model_df["SubjectID"].nunique()),
                "DesignNote": note,
            })
            if name == primary_name:
                primary_error = err

    cmp_df = pd.DataFrame(rows)
    ok_cmp = cmp_df.loc[cmp_df["Status"] == "ok"].copy()
    if ok_cmp.empty or fits.get(primary_name, {}).get("fit") is None:
        return cmp_df, pd.DataFrame(), {
            "DV": dv,
            "Domain": domain,
            "PrimaryModel": primary_name,
            "PrimaryFormula": primary_formula,
            "RecommendedModel": np.nan,
            "RecommendedFormula": np.nan,
            "n_rows": int(len(model_df)),
            "n_subjects": int(model_df["SubjectID"].nunique()) if not model_df.empty else 0,
            "Status": "failed",
            "Error": primary_error or "no successful fits",
            "DesignNote": note,
        }

    ok_cmp = ok_cmp.sort_values("AIC").reset_index(drop=True)
    recommended_name = str(ok_cmp.iloc[0]["Model"])
    fit = fits[primary_name]["fit"]
    fixed_df = _extract_coef_table(fit)
    if not fixed_df.empty:
        fixed_df.insert(0, "DV", dv)
        fixed_df.insert(1, "Domain", domain)
    summary = {
        "DV": dv,
        "Domain": domain,
        "PrimaryModel": primary_name,
        "PrimaryFormula": primary_formula,
        "RecommendedModel": recommended_name,
        "RecommendedFormula": fits[recommended_name]["formula"],
        "n_rows": int(len(model_df)),
        "n_subjects": int(model_df["SubjectID"].nunique()),
        "Status": "ok",
        "Error": "",
        "DesignNote": note,
        "SignificantTerms_p_lt_0_05": int((fixed_df["p"] < 0.05).sum()) if not fixed_df.empty else 0,
    }
    cmp_df = cmp_df.sort_values(["DV", "Status", "AIC"], na_position="last").reset_index(drop=True)
    return cmp_df, fixed_df, summary


def _plot_domain_summary(summary_df: pd.DataFrame, out_png: Path, title: str) -> str | None:
    if summary_df.empty:
        return None
    x = summary_df.copy()
    x["SignificantTerms_p_lt_0_05"] = pd.to_numeric(x["SignificantTerms_p_lt_0_05"], errors="coerce").fillna(0)
    x = x.sort_values("SignificantTerms_p_lt_0_05")
    fig, ax = plt.subplots(figsize=(8.6, max(4.2, 0.38 * len(x) + 1.5)))
    colors = np.where(x["Status"].eq("ok"), "#4C78A8", "#D62728")
    ax.barh(np.arange(len(x)), x["SignificantTerms_p_lt_0_05"], color=colors)
    ax.set_yticks(np.arange(len(x)))
    ax.set_yticklabels(x["DV"], fontsize=8.5)
    ax.set_xlabel("Count of significant terms (p < 0.05)")
    ax.set_title(title)
    out_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_png, dpi=230, bbox_inches="tight")
    plt.close(fig)
    return str(out_png)


def _write_domain_readme(base: Path, domain: str, summary_df: pd.DataFrame, note: str) -> str:
    lines = [
        f"# {domain} item-level significance",
        "",
        note,
        "",
        "## Main outputs",
        f"- `./csv/{domain}_model_comparison.csv`",
        f"- `./csv/{domain}_primary_fixed_effects.csv`",
        f"- `./csv/{domain}_primary_main_interactions.csv`",
        f"- `./md/{domain}_summary.md`",
        f"- `./png/{domain}_significant_terms.png`",
        "",
    ]
    if summary_df.empty:
        lines.append("No valid rows.")
    else:
        lines.append("## Per-DV quick summary")
        lines.append(summary_df.to_markdown(index=False, floatfmt='.4f'))
    path = base / "README.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return str(path)


def _export_domain(out: Path, domain: str, df: pd.DataFrame, dv_cols: list[str], note: str) -> list[str]:
    base = out / domain
    csv_dir = base / "csv"
    md_dir = base / "md"
    png_dir = base / "png"
    json_dir = base / "json"
    for d in [csv_dir, md_dir, png_dir, json_dir]:
        d.mkdir(parents=True, exist_ok=True)

    cmp_all = []
    fixed_all = []
    summary_rows = []
    for dv in [c for c in dv_cols if c in df.columns]:
        cmp_df, fixed_df, summary = _run_one_dv(df, domain, dv)
        cmp_all.append(cmp_df)
        if not fixed_df.empty:
            fixed_all.append(fixed_df)
        summary_rows.append(summary)

    cmp_all_df = pd.concat(cmp_all, ignore_index=True) if cmp_all else pd.DataFrame()
    fixed_all_df = pd.concat(fixed_all, ignore_index=True) if fixed_all else pd.DataFrame()
    summary_df = pd.DataFrame(summary_rows)
    infer_df = fixed_all_df.loc[fixed_all_df["EffectType"].isin(["Main Effect", "Interaction (2-way)", "Interaction (3-way)", "Interaction (4-way+)"])].copy() if not fixed_all_df.empty else pd.DataFrame()

    cmp_path = csv_dir / f"{domain}_model_comparison.csv"
    fixed_path = csv_dir / f"{domain}_primary_fixed_effects.csv"
    infer_path = csv_dir / f"{domain}_primary_main_interactions.csv"
    summary_path = csv_dir / f"{domain}_summary.csv"
    md_path = md_dir / f"{domain}_summary.md"
    png_path = png_dir / f"{domain}_significant_terms.png"
    json_path = json_dir / f"{domain}_summary.json"

    cmp_all_df.to_csv(cmp_path, index=False, encoding="utf-8-sig")
    fixed_all_df.to_csv(fixed_path, index=False, encoding="utf-8-sig")
    infer_df.to_csv(infer_path, index=False, encoding="utf-8-sig")
    summary_df.to_csv(summary_path, index=False, encoding="utf-8-sig")

    md_lines = [f"# {domain} item-level significance summary", "", note, ""]
    if summary_df.empty:
        md_lines.append("No valid rows.")
    else:
        md_lines.append("## Per-DV summary")
        md_lines.append(summary_df.to_markdown(index=False, floatfmt='.4f'))
        if not infer_df.empty:
            md_lines += ["", "## Primary-model main / interaction effects", infer_df.to_markdown(index=False, floatfmt='.4f')]
    md_path.write_text("\n".join(md_lines), encoding="utf-8")

    _plot_domain_summary(summary_df, png_path, title=f"{domain} significant terms (primary model)")
    readme_path = _write_domain_readme(base, domain, summary_df, note)

    json_path.write_text(json.dumps({
        "domain": domain,
        "n_dv": int(len(summary_df)),
        "status_ok": int((summary_df.get("Status") == "ok").sum()) if not summary_df.empty else 0,
        "note": note,
        "files": {
            "model_comparison_csv": str(cmp_path),
            "primary_fixed_effects_csv": str(fixed_path),
            "primary_main_interactions_csv": str(infer_path),
            "summary_csv": str(summary_path),
            "summary_md": str(md_path),
            "summary_png": str(png_path),
            "readme_md": str(readme_path),
        },
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    return [str(cmp_path), str(fixed_path), str(infer_path), str(summary_path), str(md_path), str(png_path), str(readme_path), str(json_path)]


def _write_root_readme(out: Path) -> str:
    lines = [
        "# Item-level significance overview",
        "",
        "This is a first-class significance branch alongside the Afford4 core model.",
        "It runs item-level / indicator-level mixed-model significance for:",
        "",
        "- S1–S5",
        "- B1–B3",
        "- IPQ1–IPQ6",
        "",
        "## Read in this order",
        "1. `./s_items/README.md`",
        "2. `./b_items/README.md`",
        "3. `./ipq_items/README.md`",
        "",
        "## Modeling notes",
        "- S items and IPQ items use the 3-factor core model: WWR, Complexity, ExperienceGroup.",
        "- B items are analyzed on the Complexity=1 subset by design, so their item-level model uses WWR and ExperienceGroup.",
    ]
    path = out / "README.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return str(path)


def main():
    ap = argparse.ArgumentParser(description="Item-level significance for S/B/IPQ (parallel in status to Afford4 core model)")
    ap.add_argument("--long-csv", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, default=Path("results/significance/item_level"))
    ap.add_argument("--exclude-subjects", default="")
    args = ap.parse_args()

    apply_bae_style()

    out = args.out_dir
    out.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(args.long_csv)
    df = _exclude_subjects(df, args.exclude_subjects)

    outputs: list[str] = []
    outputs += _export_domain(out, "s_items", df, S_COLS, note="S1–S5 use the same 3-factor item-level LMM structure as the questionnaire core model.")
    outputs += _export_domain(out, "b_items", df, B_COLS, note="B1–B3 are modeled on the Complexity=1 subset by design; Complexity is therefore held constant rather than entered again.")
    outputs += _export_domain(out, "ipq_items", df, IPQ_COLS, note="IPQ1–IPQ6 use the same 3-factor item-level LMM structure as the questionnaire core model.")
    root_readme = _write_root_readme(out)
    outputs.append(root_readme)

    payload = {
        "task": "item level significance",
        "scope": ["s_items", "b_items", "ipq_items"],
        "outputs": outputs,
        "note": "Item-level significance is now modeled as a first-class branch alongside Afford4. IPQ covers IPQ1–IPQ6 explicitly.",
    }
    (out / "item_level_significance_summary.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False))


if __name__ == "__main__":
    main()
