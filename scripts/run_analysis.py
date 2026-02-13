#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import argparse
import json
import re
import warnings

import numpy as np
import pandas as pd
import pingouin as pg
import yaml
import seaborn as sns
import matplotlib.pyplot as plt
from statsmodels.formula.api import mixedlm

warnings.filterwarnings("ignore")

S_ITEM_PATTERN = re.compile(r"^Q(?P<block>\d+)\.(?P<item>[1-5])_S(?P<sidx>[1-5])\.")


def cronbach_alpha(df: pd.DataFrame) -> float:
    x = df.dropna()
    if x.shape[1] < 2 or x.shape[0] < 3:
        return np.nan
    return float(pg.cronbach_alpha(data=x)[0])


def load_cfg(path: Path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def detect_s_item_columns(columns):
    by_block = {}
    for col in columns:
        m = S_ITEM_PATTERN.match(str(col))
        if not m:
            continue
        b = int(m.group("block"))
        i = int(m.group("item"))
        by_block.setdefault(b, {})[i] = col
    return by_block


def reshape_to_long(df: pd.DataFrame, cfg: dict):
    cols = cfg["columns"]
    subj_col = cols["subject"]
    freq_col = cols.get("frequency")
    order_col = cols.get("scene_order_code")

    detected = detect_s_item_columns(df.columns)
    scene_blocks = cfg.get("scene_blocks", [2, 3, 4, 5, 6, 7, 9, 10, 11, 12, 13, 14])

    rows = []
    for _, r in df.iterrows():
        sid = r.get(subj_col)
        freq = r.get(freq_col) if freq_col else np.nan
        order_code = r.get(order_col) if order_col else np.nan

        for b in scene_blocks:
            block_cols = detected.get(b, {})
            if len(block_cols) < 5:
                continue

            vals = []
            for item in [1, 2, 3, 4, 5]:
                v = pd.to_numeric(r.get(block_cols[item]), errors="coerce")
                vals.append(v)

            round_id = 1 if b <= 7 else 2
            scene_idx = (b - 1) if b <= 7 else (b - 8)  # 1..6 in each round

            rec = {
                "subject": sid,
                "frequency": freq,
                "scene_order_code": order_code,
                "round": round_id,
                "scene_index": scene_idx,
                "q_block": b,
                "S1": vals[0],
                "S2": vals[1],
                "S3": vals[2],
                "S4": vals[3],
                "S5": vals[4],
                "affordance_score": np.nanmean(vals),
            }

            cond_map = cfg.get("scene_condition_map", {})
            cm = cond_map.get(scene_idx, cond_map.get(str(scene_idx), {}))
            rec["wwr"] = cm.get("wwr")
            rec["complexity"] = cm.get("complexity")
            rows.append(rec)

    out = pd.DataFrame(rows)
    return out


def run_model(df_long: pd.DataFrame):
    x = df_long.dropna(subset=["subject", "affordance_score"]).copy()
    has_cond = x["wwr"].notna().any() and x["complexity"].notna().any()

    if has_cond:
        formula = "affordance_score ~ C(wwr) * C(complexity) * C(frequency) + C(round)"
    else:
        formula = "affordance_score ~ C(scene_index) * C(frequency) + C(round)"

    fit = mixedlm(formula=formula, data=x, groups=x["subject"]).fit(reml=False, method="lbfgs", maxiter=1000)
    return fit, formula


def export_plot(df_long: pd.DataFrame, out_png: Path):
    x = df_long.copy()
    out_png.parent.mkdir(parents=True, exist_ok=True)

    if x["wwr"].notna().any() and x["complexity"].notna().any():
        plt.figure(figsize=(8, 5))
        sns.pointplot(data=x, x="wwr", y="affordance_score", hue="complexity", errorbar="se", dodge=True)
        plt.title("WWR × 信息复杂度 on 可供性感知")
    else:
        plt.figure(figsize=(8, 5))
        sns.pointplot(data=x, x="scene_index", y="affordance_score", hue="round", errorbar="se", dodge=True)
        plt.title("Scene × Round on 可供性感知")

    plt.tight_layout()
    plt.savefig(out_png, dpi=200)
    plt.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", type=Path, default=Path("config/config.yaml"))
    ap.add_argument("--out", type=Path, default=Path("results/run1"))
    args = ap.parse_args()

    cfg = load_cfg(args.config)
    out = args.out
    out.mkdir(parents=True, exist_ok=True)

    raw = pd.read_excel(cfg["coded_excel"], sheet_name=cfg.get("sheet_name", 0))
    long_df = reshape_to_long(raw, cfg)

    alpha = cronbach_alpha(long_df[["S1", "S2", "S3", "S4", "S5"]])
    fit, formula = run_model(long_df)

    long_df.to_csv(out / "long_data.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame({"alpha_S1_S5": [alpha]}).to_csv(out / "reliability.csv", index=False, encoding="utf-8-sig")
    (out / "model_formula.txt").write_text(formula, encoding="utf-8")
    (out / "lmm_summary.txt").write_text(str(fit.summary()), encoding="utf-8")

    desc = (
        long_df.groupby(["round", "scene_index"], dropna=False)["affordance_score"]
        .agg(["count", "mean", "std"])
        .reset_index()
    )
    desc.to_csv(out / "descriptives_by_scene.csv", index=False, encoding="utf-8-sig")

    export_plot(long_df, out / "figures" / "interaction.png")

    report = {
        "n_raw_rows": int(raw.shape[0]),
        "n_long_rows": int(long_df.shape[0]),
        "alpha_S1_S5": None if np.isnan(alpha) else float(alpha),
        "formula": formula,
    }
    (out / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Done: {out}")


if __name__ == "__main__":
    main()
