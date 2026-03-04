#!/usr/bin/env python3
from __future__ import annotations

"""Analysis-2 Task2: core_Imm_suite (核心 LMM：主效应/交互).

目标：围绕 factor_WWR（以及相关因素 Complexity、Group）跑分层模型，覆盖 S1-S5 与 B1-B3。

S-items（S1-S5）模型：
- Model1: 主效应（WWR + Complexity + Group）
- Model2: 两两交互（WWR:Complexity, WWR:Group, Complexity:Group）
- Model3: 三阶交互（WWR:Complexity:Group）

B-items（B1-B3）模型（按设计仅 C1 有效，需调整）：
- 先过滤 Complexity == 1
- Model1: 主效应（WWR + Group）
- Model2: 两两交互（WWR:Group）
- Model3: 三阶交互不适用（记录为 skipped）

输出（默认 results/research）：
- analysis2_core_imm_suite_s_effects.csv
- analysis2_core_imm_suite_s_models.csv
- analysis2_core_imm_suite_b_effects.csv
- analysis2_core_imm_suite_b_models.csv
- analysis2_core_imm_suite_summary.json
"""

from pathlib import Path
import argparse
import json
import warnings

import numpy as np
import pandas as pd
from statsmodels.formula.api import mixedlm
from statsmodels.stats.multitest import multipletests

from analysis_groups import make_people_group4

warnings.filterwarnings("ignore")

S_DVS = ["S1", "S2", "S3", "S4", "S5"]
B_DVS = ["B1", "B2", "B3"]


def _sigstar(p: float | None) -> str:
    if p is None or pd.isna(p):
        return ""
    if p < 0.001:
        return "***"
    if p < 0.01:
        return "**"
    if p < 0.05:
        return "*"
    return ""


def _fit_with_fallback(data: pd.DataFrame, formula: str, random_slope_complexity: bool = True):
    attempts = []
    if random_slope_complexity:
        attempts.extend([
            {"method": "lbfgs", "re_formula": "1 + C(Complexity)"},
            {"method": "powell", "re_formula": "1 + C(Complexity)"},
        ])
    attempts.extend([
        {"method": "lbfgs", "re_formula": None},
        {"method": "powell", "re_formula": None},
    ])

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
            continue

    raise RuntimeError(f"MixedLM failed. formula={formula}; last_error={last_err}")


def _extract_effects(dv: str, domain: str, model_name: str, formula: str, fit) -> pd.DataFrame:
    ci = fit.conf_int()
    rows = []
    for term in fit.params.index:
        if term.startswith("Group Var") or " Var" in term or " Cov" in term:
            continue
        rows.append({
            "Domain": domain,
            "DV": dv,
            "Model": model_name,
            "Formula": formula,
            "Term": term,
            "Coef": fit.params[term],
            "SE": fit.bse[term],
            "z": fit.tvalues[term],
            "p": fit.pvalues[term],
            "CI95_low": ci.loc[term, 0] if term in ci.index else np.nan,
            "CI95_high": ci.loc[term, 1] if term in ci.index else np.nan,
        })

    out = pd.DataFrame(rows)
    if out.empty:
        return out

    # Holm correction within DV x Model over non-intercept fixed terms.
    out["p_holm"] = np.nan
    mask = out["Term"] != "Intercept"
    if mask.any():
        pv = out.loc[mask, "p"].to_numpy(dtype=float)
        ok = np.isfinite(pv)
        if ok.any():
            _, corr, _, _ = multipletests(pv[ok], method="holm")
            tgt = out.loc[mask].index.to_numpy()[ok]
            out.loc[tgt, "p_holm"] = corr

    out["sig_holm"] = out["p_holm"].apply(_sigstar)
    return out


def _run_suite(
    df: pd.DataFrame,
    dvs: list[str],
    domain: str,
    group_col: str,
    model_specs: list[tuple[str, str]],
    random_slope_complexity: bool,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    all_effects = []
    model_rows = []

    for dv in dvs:
        if dv not in df.columns:
            continue

        for model_name, formula_tpl in model_specs:
            if formula_tpl == "SKIP":
                model_rows.append({
                    "Domain": domain,
                    "DV": dv,
                    "Model": model_name,
                    "Formula": "SKIP",
                    "Status": "skipped_not_identifiable",
                    "Reason": "Model requires Complexity terms, but B-items are C1-only by design.",
                    "n_rows": int(df[dv].notna().sum()),
                    "n_subjects": int(df.loc[df[dv].notna(), "SubjectID"].nunique()),
                })
                continue

            formula = formula_tpl.format(dv=dv, g=group_col)
            need_cols = ["SubjectID", "WWR", group_col, dv]
            if "Complexity" in formula:
                need_cols.append("Complexity")

            sub = df.dropna(subset=need_cols).copy()
            if sub.empty or sub["SubjectID"].nunique() < 3:
                model_rows.append({
                    "Domain": domain,
                    "DV": dv,
                    "Model": model_name,
                    "Formula": formula,
                    "Status": "skipped_insufficient_data",
                    "Reason": "Not enough rows or subjects after filtering.",
                    "n_rows": int(len(sub)),
                    "n_subjects": int(sub["SubjectID"].nunique()) if not sub.empty else 0,
                })
                continue

            for c in ["WWR", group_col]:
                sub[c] = sub[c].astype(str)
            if "Complexity" in sub.columns:
                sub["Complexity"] = sub["Complexity"].astype(str)

            try:
                fit, info = _fit_with_fallback(sub, formula, random_slope_complexity=random_slope_complexity)
                eff = _extract_effects(dv=dv, domain=domain, model_name=model_name, formula=formula, fit=fit)
                if not eff.empty:
                    all_effects.append(eff)

                model_rows.append({
                    "Domain": domain,
                    "DV": dv,
                    "Model": model_name,
                    "Formula": formula,
                    "Status": "ok",
                    "Reason": "",
                    "n_rows": int(len(sub)),
                    "n_subjects": int(sub["SubjectID"].nunique()),
                    "fit_method": info["fit_method"],
                    "re_formula_used": info["re_formula_used"],
                    "fallback_to_random_intercept": bool(info["fallback_to_random_intercept"]),
                    "converged": bool(info["converged"]),
                    "AIC": info["aic"],
                    "BIC": info["bic"],
                    "LogLik": info["llf"],
                })
            except Exception as e:
                model_rows.append({
                    "Domain": domain,
                    "DV": dv,
                    "Model": model_name,
                    "Formula": formula,
                    "Status": "failed",
                    "Reason": str(e),
                    "n_rows": int(len(sub)),
                    "n_subjects": int(sub["SubjectID"].nunique()),
                })

    eff_df = pd.concat(all_effects, ignore_index=True) if all_effects else pd.DataFrame()
    mdl_df = pd.DataFrame(model_rows)
    return eff_df, mdl_df


def main():
    ap = argparse.ArgumentParser(description="Analysis-2 Task2 core_Imm_suite: layered LMM for S1-S5 and B1-B3")
    ap.add_argument("--long-csv", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, default=Path("results/research"))
    ap.add_argument("--group-col", default="PeopleGroup4", help="Group column for factor_Group")
    args = ap.parse_args()

    out = args.out_dir
    out.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(args.long_csv)

    # ensure common fields
    if "SubjectID" not in df.columns:
        raise SystemExit("Missing required column: SubjectID")
    if "WWR" not in df.columns:
        raise SystemExit("Missing required column: WWR")

    # build default 4-group if needed
    if args.group_col == "PeopleGroup4" and "PeopleGroup4" not in df.columns:
        df = make_people_group4(df)

    if args.group_col not in df.columns:
        raise SystemExit(f"Missing group column: {args.group_col}")

    # S suite
    s_specs = [
        ("Model1_main", "{dv} ~ C(WWR) + C(Complexity) + C({g})"),
        ("Model2_two_way", "{dv} ~ C(WWR) * C(Complexity) + C(WWR) * C({g}) + C(Complexity) * C({g})"),
        ("Model3_three_way", "{dv} ~ C(WWR) * C(Complexity) * C({g})"),
    ]

    s_df = df.copy()
    if "Complexity" not in s_df.columns:
        raise SystemExit("Missing required column for S-models: Complexity")

    s_eff, s_models = _run_suite(
        df=s_df,
        dvs=S_DVS,
        domain="S",
        group_col=args.group_col,
        model_specs=s_specs,
        random_slope_complexity=True,
    )

    # B suite (C1-only adjustment)
    b_df = df.copy()
    if "Complexity" in b_df.columns:
        b_df["Complexity"] = pd.to_numeric(b_df["Complexity"], errors="coerce")
        # Design check: B values should not appear outside C1.
        for dv in B_DVS:
            if dv in b_df.columns:
                bad = b_df[(b_df["Complexity"] != 1) & (pd.to_numeric(b_df[dv], errors="coerce").notna())]
                if len(bad) > 0:
                    raise SystemExit(
                        f"Found non-NA {dv} values in Complexity!=1 rows. This violates design (B-items are C1-only)."
                    )
        b_df = b_df[b_df["Complexity"] == 1].copy()

    b_specs = [
        ("Model1_main_adj", "{dv} ~ C(WWR) + C({g})"),
        ("Model2_two_way_adj", "{dv} ~ C(WWR) * C({g})"),
        ("Model3_three_way_adj", "SKIP"),
    ]

    b_eff, b_models = _run_suite(
        df=b_df,
        dvs=B_DVS,
        domain="B",
        group_col=args.group_col,
        model_specs=b_specs,
        random_slope_complexity=False,
    )

    s_eff_path = out / "analysis2_core_imm_suite_s_effects.csv"
    s_models_path = out / "analysis2_core_imm_suite_s_models.csv"
    b_eff_path = out / "analysis2_core_imm_suite_b_effects.csv"
    b_models_path = out / "analysis2_core_imm_suite_b_models.csv"

    s_eff.to_csv(s_eff_path, index=False, encoding="utf-8-sig")
    s_models.to_csv(s_models_path, index=False, encoding="utf-8-sig")
    b_eff.to_csv(b_eff_path, index=False, encoding="utf-8-sig")
    b_models.to_csv(b_models_path, index=False, encoding="utf-8-sig")

    summary = {
        "task": "analysis-2/task2 core_imm_suite",
        "group_col": args.group_col,
        "s_dvs": [dv for dv in S_DVS if dv in df.columns],
        "b_dvs": [dv for dv in B_DVS if dv in df.columns],
        "outputs": [
            str(s_eff_path.relative_to(out)),
            str(s_models_path.relative_to(out)),
            str(b_eff_path.relative_to(out)),
            str(b_models_path.relative_to(out)),
        ],
        "notes": [
            "S-items: Model1/2/3 include WWR, Complexity, Group (up to 3-way interaction).",
            "B-items are C1-only by design; adjusted to WWR + Group models.",
            "B Model3 is marked skipped_not_identifiable.",
        ],
    }

    (out / "analysis2_core_imm_suite_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
