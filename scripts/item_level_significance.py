#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import argparse
import json

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from scipy.stats import ttest_ind
from statsmodels.stats.multitest import multipletests

from plot_style import apply_bae_style

QC_EXCLUDE = "孙校聪,康少勇,张钰鹏,杨可,洪婷婷,陈韬,高梓楠,赵国宏"
S_COLS = ["S1", "S2", "S3", "S4", "S5"]
B_COLS = ["B1", "B2", "B3", "Bmean"]
IPQ_COLS = ["IPQ1", "IPQ2", "IPQ3", "IPQ4", "IPQ5", "IPQ6", "IPQ_mean"]


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


def _summary_box(ax, title: str, lines: list[str]):
    ax.axis("off")
    ax.set_facecolor("#F7FAF8")
    ax.text(0.03, 0.97, title, va="top", ha="left", fontsize=10.2, fontweight="bold", color="#40534C")
    ax.text(
        0.03, 0.90, "\n".join(lines), va="top", ha="left", fontsize=8.8, color="#50615A", linespacing=1.36,
        bbox=dict(boxstyle="round,pad=0.45", fc="#F4F8F6", ec="#D5DFD9", lw=0.8)
    )


def _welch_by_experience(subject_df: pd.DataFrame, dv_cols: list[str]) -> pd.DataFrame:
    rows = []
    pvals = []
    for dv in [c for c in dv_cols if c in subject_df.columns]:
        sub = subject_df.dropna(subset=["ExperienceGroup", dv]).copy()
        groups = sorted(sub["ExperienceGroup"].astype(str).unique())
        if len(groups) != 2:
            rows.append({"DV": dv, "GroupA": np.nan, "GroupB": np.nan, "p": np.nan})
            pvals.append(np.nan)
            continue
        g1, g2 = groups[0], groups[1]
        v1 = sub.loc[sub["ExperienceGroup"].astype(str) == g1, dv].to_numpy(dtype=float)
        v2 = sub.loc[sub["ExperienceGroup"].astype(str) == g2, dv].to_numpy(dtype=float)
        v1 = v1[np.isfinite(v1)]
        v2 = v2[np.isfinite(v2)]
        if len(v1) < 3 or len(v2) < 3:
            t, p = np.nan, np.nan
        else:
            r = ttest_ind(v1, v2, equal_var=False, nan_policy="omit")
            t, p = float(r.statistic), float(r.pvalue)
        rows.append({
            "DV": dv,
            "GroupA": g1,
            "GroupB": g2,
            "nA": int(len(v1)),
            "nB": int(len(v2)),
            "meanA": float(np.mean(v1)) if len(v1) else np.nan,
            "meanB": float(np.mean(v2)) if len(v2) else np.nan,
            "delta_A_minus_B": float(np.mean(v1) - np.mean(v2)) if len(v1) and len(v2) else np.nan,
            "t_welch": t,
            "p": p,
        })
        pvals.append(p)
    out = pd.DataFrame(rows)
    mask = out["p"].notna()
    out["p_holm"] = np.nan
    if mask.any():
        out.loc[mask, "p_holm"] = multipletests(out.loc[mask, "p"].astype(float), method="holm")[1]
    out["sig_holm"] = out["p_holm"].map(_sigstar)
    return out


def _subject_level(df: pd.DataFrame, dv_cols: list[str], keep_c1_only: bool = False) -> pd.DataFrame:
    x = df.copy()
    if keep_c1_only and "Complexity" in x.columns:
        x = x[pd.to_numeric(x["Complexity"], errors="coerce") == 1].copy()
    keep = [c for c in ["SubjectID", "ExperienceGroup"] + dv_cols if c in x.columns]
    x = x[keep].copy()
    agg = {c: "mean" for c in dv_cols if c in x.columns}
    agg.update({"ExperienceGroup": "first"})
    return x.groupby("SubjectID", as_index=False).agg(agg)


def _plot_welch_results(df: pd.DataFrame, out_png: Path, title: str) -> str | None:
    if df.empty or "p_holm" not in df.columns:
        return None
    x = df.dropna(subset=["p_holm"]).copy()
    if x.empty:
        return None
    x["minuslog10p"] = -np.log10(x["p_holm"].clip(lower=1e-300))
    x = x.sort_values("minuslog10p")

    fig = plt.figure(figsize=(9.6, max(4.6, 0.38 * len(x) + 1.8)))
    gs = fig.add_gridspec(1, 2, width_ratios=[3.6, 1.4], wspace=0.14)
    ax = fig.add_subplot(gs[0, 0])
    ax2 = fig.add_subplot(gs[0, 1])
    ax.barh(np.arange(len(x)), x["minuslog10p"], color="#8EC5B6")
    ax.set_yticks(np.arange(len(x)))
    ax.set_yticklabels(x["DV"], fontsize=8.5)
    ax.set_xlabel("-log10(Holm p)")
    ax.set_title(title)

    top = x.iloc[-1]
    _summary_box(ax2, "Item-level significance", [
        f"Rows: {len(x)}",
        f"Top item: {top['DV']}",
        f"Holm p={top['p_holm']:.3f}",
        f"delta={top.get('delta_A_minus_B', np.nan):.3f}",
    ])
    out_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_png, dpi=230)
    plt.close(fig)
    return str(out_png)


def _write_md(df: pd.DataFrame, out_md: Path, title: str):
    lines = [f"# {title}", ""]
    if df.empty:
        lines.append("No valid rows.")
    else:
        lines.append(df.to_markdown(index=False, floatfmt='.4f'))
    out_md.write_text("\n".join(lines), encoding="utf-8")


def _export_block(base: Path, name: str, df: pd.DataFrame) -> list[str]:
    csv_dir = base / name / "csv"
    png_dir = base / name / "png"
    md_dir = base / name / "md"
    json_dir = base / name / "json"
    for d in [csv_dir, png_dir, md_dir, json_dir]:
        d.mkdir(parents=True, exist_ok=True)

    csv_path = csv_dir / f"{name}_experience_welch.csv"
    md_path = md_dir / f"{name}_experience_welch.md"
    png_path = png_dir / f"{name}_experience_welch.png"
    json_path = json_dir / f"{name}_summary.json"

    df.to_csv(csv_path, index=False, encoding="utf-8-sig")
    _write_md(df, md_path, f"{name} experience significance")
    _plot_welch_results(df, png_path, title=f"{name} experience significance")
    json_path.write_text(json.dumps({
        "name": name,
        "n_rows": int(len(df)),
        "csv": str(csv_path),
        "md": str(md_path),
        "png": str(png_path),
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    return [str(csv_path), str(md_path), str(png_path), str(json_path)]


def main():
    ap = argparse.ArgumentParser(description="Item-level significance for S/B/IPQ (overall + experience)")
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

    # S items (subject-level means across repeated rows; experience Welch as current main-compatible simple significance line)
    s_subj = _subject_level(df, S_COLS, keep_c1_only=False)
    s_res = _welch_by_experience(s_subj, S_COLS)
    outputs += _export_block(out / "experience", "s_items", s_res)

    # B items (C1 only)
    b_subj = _subject_level(df, B_COLS, keep_c1_only=True)
    b_res = _welch_by_experience(b_subj, B_COLS)
    outputs += _export_block(out / "experience", "b_items", b_res)

    # IPQ items (subject-level)
    ipq_subj = _subject_level(df, IPQ_COLS, keep_c1_only=False)
    ipq_res = _welch_by_experience(ipq_subj, IPQ_COLS)
    outputs += _export_block(out / "experience", "ipq_items", ipq_res)

    # overall item-level descriptively-significant bundle can be kept as subject-level tables without between-group test
    overall_csv = out / "overall" / "csv"
    overall_csv.mkdir(parents=True, exist_ok=True)
    s_subj.to_csv(overall_csv / "s_items_subject_level.csv", index=False, encoding="utf-8-sig")
    b_subj.to_csv(overall_csv / "b_items_subject_level.csv", index=False, encoding="utf-8-sig")
    ipq_subj.to_csv(overall_csv / "ipq_items_subject_level.csv", index=False, encoding="utf-8-sig")
    outputs += [
        str(overall_csv / "s_items_subject_level.csv"),
        str(overall_csv / "b_items_subject_level.csv"),
        str(overall_csv / "ipq_items_subject_level.csv"),
    ]

    payload = {
        "task": "item level significance",
        "scope": ["overall", "experience"],
        "outputs": outputs,
        "note": "Current main-compatible item-level significance uses experience-group Welch tests for S/B/IPQ subject-level summaries.",
    }
    (out / "item_level_significance_summary.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False))


if __name__ == "__main__":
    main()
