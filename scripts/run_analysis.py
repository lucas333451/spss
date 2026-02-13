#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path
import argparse
import json
import warnings

import numpy as np
import pandas as pd
import pingouin as pg
import yaml
import seaborn as sns
import matplotlib.pyplot as plt
from statsmodels.formula.api import mixedlm

warnings.filterwarnings("ignore")


def cronbach_alpha(df: pd.DataFrame) -> float:
    df = df.dropna()
    if df.shape[1] < 2 or df.shape[0] < 3:
        return np.nan
    return float(pg.cronbach_alpha(data=df)[0])


def load_cfg(path: Path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def load_data(cfg):
    df = pd.read_excel(cfg["coded_excel"], sheet_name=cfg.get("sheet_name", 0))
    return df


def clean_data(df: pd.DataFrame, cfg: dict):
    c = cfg["columns"]
    out = df.copy()

    if c.get("attention_pass"):
        before = len(out)
        out = out[out[c["attention_pass"]] == cfg.get("attention_pass_value", 1)]
        after = len(out)
    else:
        before, after = len(out), len(out)

    log = {"n_raw": int(before), "n_clean": int(after), "dropped": int(before - after)}
    return out, log


def build_scores(df: pd.DataFrame, cfg: dict):
    c = cfg["columns"]
    item_cols = c["instant_items"]
    df = df.copy()
    df["affordance_score"] = df[item_cols].mean(axis=1)
    return df


def descriptives(df: pd.DataFrame, cfg: dict):
    c = cfg["columns"]
    grp = [c["wwr"], c["complexity"], c["frequency"]]
    d = df.groupby(grp, dropna=False)["affordance_score"].agg(["count", "mean", "std"]).reset_index()
    return d


def run_lmm(df: pd.DataFrame, cfg: dict):
    c = cfg["columns"]
    formula = (
        f"affordance_score ~ C({c['wwr']}) * C({c['complexity']}) * C({c['frequency']})"
        + (f" + C({c['round']})" if c.get("round") else "")
    )
    model = mixedlm(formula=formula, data=df, groups=df[c["subject"]])
    fit = model.fit(reml=False, method="lbfgs", maxiter=1000)
    return fit


def plot_interaction(df: pd.DataFrame, cfg: dict, out_png: Path):
    c = cfg["columns"]
    plt.figure(figsize=(8, 5))
    sns.pointplot(
        data=df,
        x=c["wwr"],
        y="affordance_score",
        hue=c["complexity"],
        errorbar="se",
        dodge=True,
    )
    plt.title("WWR × 信息复杂度 on 可供性感知")
    plt.tight_layout()
    out_png.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_png, dpi=200)
    plt.close()


def write_report(alpha, clean_log, fit_summary, output_dir: Path):
    lines = [
        "# Questionnaire Analysis Report",
        "",
        f"- Cronbach alpha (instant items): {alpha:.3f}" if not np.isnan(alpha) else "- Cronbach alpha: NA",
        f"- Raw N: {clean_log['n_raw']}, Clean N: {clean_log['n_clean']}, Dropped: {clean_log['dropped']}",
        "",
        "## LMM Summary",
        "```",
        fit_summary,
        "```",
    ]
    (output_dir / "report.md").write_text("\n".join(lines), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser(description="SPSS replacement pipeline for VR+EEG questionnaire")
    ap.add_argument("--config", type=Path, default=Path("config/config.example.yaml"))
    ap.add_argument("--out", type=Path, default=Path("results/run1"))
    args = ap.parse_args()

    cfg = load_cfg(args.config)
    out = args.out
    out.mkdir(parents=True, exist_ok=True)

    df = load_data(cfg)
    df_clean, clean_log = clean_data(df, cfg)
    df_score = build_scores(df_clean, cfg)

    alpha = cronbach_alpha(df_score[cfg["columns"]["instant_items"]])
    desc = descriptives(df_score, cfg)
    fit = run_lmm(df_score, cfg)

    df_score.to_csv(out / "data_scored.csv", index=False, encoding="utf-8-sig")
    desc.to_csv(out / "descriptives.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame({"metric": list(clean_log.keys()), "value": list(clean_log.values())}).to_csv(out / "cleaning_log.csv", index=False, encoding="utf-8-sig")
    (out / "lmm_summary.txt").write_text(str(fit.summary()), encoding="utf-8")
    (out / "model_formula.txt").write_text(fit.model.formula, encoding="utf-8")
    (out / "cleaning_log.json").write_text(json.dumps(clean_log, ensure_ascii=False, indent=2), encoding="utf-8")

    plot_interaction(df_score, cfg, out / "figures" / "wwr_complexity_interaction.png")
    write_report(alpha, clean_log, str(fit.summary()), out)

    print(f"Done. Output at: {out}")


if __name__ == "__main__":
    main()
