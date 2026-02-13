#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import argparse
import json
import warnings

import pandas as pd
import numpy as np
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


def main():
    ap = argparse.ArgumentParser(description="Run LMM on long-format questionnaire data")
    ap.add_argument("--long-csv", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, default=Path("results/model"))
    args = ap.parse_args()

    out = args.out_dir
    out.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(args.long_csv)

    alpha = cronbach_alpha(df[["S1", "S2", "S3", "S4", "S5"]])

    model_df = df.dropna(subset=["SubjectID", "Afford5", "WWR", "Complexity", "SportFreq"]).copy()
    formula = "Afford5 ~ C(WWR) * C(Complexity) * C(SportFreq) + C(Block) + C(Position)"
    fit = mixedlm(formula=formula, data=model_df, groups=model_df["SubjectID"]).fit(reml=False, method="lbfgs", maxiter=1000)

    # interaction plot
    plt.figure(figsize=(8, 5))
    sns.pointplot(data=model_df, x="WWR", y="Afford5", hue="Complexity", errorbar="se", dodge=True)
    plt.title("WWR × Complexity on Afford5")
    plt.tight_layout()
    (out / "figures").mkdir(parents=True, exist_ok=True)
    plt.savefig(out / "figures" / "wwr_complexity_afford5.png", dpi=200)
    plt.close()

    desc = model_df.groupby(["WWR", "Complexity", "SportFreq"], dropna=False)["Afford5"].agg(["count", "mean", "std"]).reset_index()
    desc.to_csv(out / "descriptives.csv", index=False, encoding="utf-8-sig")
    (out / "lmm_summary.txt").write_text(str(fit.summary()), encoding="utf-8")
    (out / "model_formula.txt").write_text(formula, encoding="utf-8")

    report = {
        "n_rows_input": int(len(df)),
        "n_rows_model": int(len(model_df)),
        "cronbach_alpha_s1_s5": None if np.isnan(alpha) else float(alpha),
        "formula": formula,
    }
    (out / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
