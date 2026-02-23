#!/usr/bin/env python3
from __future__ import annotations

"""One-page, journal-style diagnostics for the primary LMM (Afford4).

Outputs (under results/diagnostics by default):
- model_diagnostics.md (supplement-style page)
- figures/resid_qq.png
- figures/resid_fitted.png

Notes
- Uses statsmodels MixedLM, matching scripts/run_analysis.py.
- This is intended for transparency/audit; it is not a substitute for domain judgement.
"""

from pathlib import Path
import argparse
import json
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from statsmodels.formula.api import mixedlm


def _safe(x):
    return "NA" if x is None or (isinstance(x, float) and np.isnan(x)) else x


def _fit_primary(df: pd.DataFrame):
    # Primary model is fixed to Model_A_compact (main effects)
    formula = "Afford4 ~ C(Complexity) + C(WWR) + C(ExperienceGroup) + C(SportFreqGroup) + C(Repetition) + C(Position)"
    re_formula = "1 + C(Complexity)"

    mdl = mixedlm(formula=formula, data=df, groups=df["SubjectID"], re_formula=re_formula)
    fit = mdl.fit(reml=False, method="lbfgs", maxiter=2500)
    return fit, formula, re_formula


def _is_singular(fit, tol: float = 1e-8) -> bool:
    cov_re = getattr(fit, "cov_re", None)
    if cov_re is None:
        return False
    try:
        arr = np.asarray(cov_re, dtype=float)
        if arr.ndim != 2 or arr.shape[0] == 0:
            return False
        if np.any(np.diag(arr) <= tol):
            return True
        eig = np.linalg.eigvalsh(arr)
        return bool(np.min(eig) <= tol)
    except Exception:
        return False


def main():
    ap = argparse.ArgumentParser(description="Export one-page MixedLM diagnostics (Afford4 primary model)")
    ap.add_argument("--long-csv", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, default=Path("results/diagnostics"))
    args = ap.parse_args()

    out = args.out_dir
    fig = out / "figures"
    out.mkdir(parents=True, exist_ok=True)
    fig.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(args.long_csv)

    # required columns
    need = ["SubjectID", "S1", "S2", "S3", "S4", "WWR", "Complexity", "ExperienceGroup", "SportFreqGroup", "Position"]
    miss = [c for c in need if c not in df.columns]
    if miss:
        raise SystemExit(f"Missing required columns: {miss}")

    if "Repetition" not in df.columns:
        df["Repetition"] = df["Block"] if "Block" in df.columns else np.nan

    # main DV
    df["Afford4"] = df[["S1", "S2", "S3", "S4"]].mean(axis=1)

    # Fit
    fit, formula, re_formula = _fit_primary(df.dropna(subset=["Afford4", "SubjectID"]).copy())

    # Residuals and fitted
    fitted = np.asarray(fit.fittedvalues, dtype=float)
    resid = np.asarray(fit.resid, dtype=float)

    # Standardized residuals (approx)
    resid_std = (resid - np.nanmean(resid)) / (np.nanstd(resid, ddof=1) + 1e-12)

    # QQ plot
    import scipy.stats as st

    plt.figure(figsize=(5.4, 5.4))
    st.probplot(resid_std, dist="norm", plot=plt)
    plt.title("Residual QQ (standardized)")
    plt.tight_layout()
    plt.savefig(fig / "resid_qq.png", dpi=220)
    plt.close()

    # Residual vs fitted
    plt.figure(figsize=(6.4, 4.6))
    sns.scatterplot(x=fitted, y=resid, s=18, alpha=0.6, edgecolor=None)
    sns.regplot(x=fitted, y=resid, scatter=False, lowess=True, color="red")
    plt.axhline(0, color="black", lw=1)
    plt.xlabel("Fitted values")
    plt.ylabel("Residuals")
    plt.title("Residuals vs Fitted (LOESS)")
    plt.tight_layout()
    plt.savefig(fig / "resid_fitted.png", dpi=220)
    plt.close()

    # Summary stats
    meta = {
        "formula": formula,
        "random_structure_requested": "(1 + Complexity | Subject)",
        "random_structure_used": "(1 + Complexity | Subject)",
        "fit_method": "lbfgs",
        "reml": False,
        "converged": bool(getattr(fit, "converged", True)),
        "singular": _is_singular(fit),
        "aic": float(getattr(fit, "aic", np.nan)),
        "bic": float(getattr(fit, "bic", np.nan)),
        "loglik": float(getattr(fit, "llf", np.nan)),
        "n_rows": int(df.dropna(subset=["Afford4"]).shape[0]),
        "n_subjects": int(df["SubjectID"].nunique()),
    }

    (out / "model_diagnostics_meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    md = []
    md.append("# Model diagnostics (Supplement)")
    md.append("")
    md.append("This page provides basic, journal-style diagnostics for the **primary** LMM (Afford4).")
    md.append("")
    md.append("## Fit summary")
    md.append(f"- Formula: `{meta['formula']}`")
    md.append(f"- Random structure: requested `{meta['random_structure_requested']}`; used `{meta['random_structure_used']}`")
    md.append(f"- Converged: `{meta['converged']}`")
    md.append(f"- Singular (heuristic): `{meta['singular']}`")
    md.append(f"- AIC: `{_safe(meta['aic'])}`; BIC: `{_safe(meta['bic'])}`; LogLik: `{_safe(meta['loglik'])}`")
    md.append(f"- N rows: `{meta['n_rows']}`; N subjects: `{meta['n_subjects']}`")
    md.append("")
    md.append("## Residual diagnostics")
    md.append("- QQ plot: `figures/resid_qq.png`")
    md.append("- Residuals vs fitted: `figures/resid_fitted.png`")
    md.append("")
    md.append("![Residual QQ](figures/resid_qq.png)")
    md.append("")
    md.append("![Residuals vs Fitted](figures/resid_fitted.png)")

    (out / "model_diagnostics.md").write_text("\n".join(md), encoding="utf-8")

    print(json.dumps({
        "out_dir": str(out),
        "outputs": [
            "model_diagnostics.md",
            "model_diagnostics_meta.json",
            "figures/resid_qq.png",
            "figures/resid_fitted.png",
        ],
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
