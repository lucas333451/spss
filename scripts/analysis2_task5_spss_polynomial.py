#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import argparse
import json

import numpy as np
import pandas as pd
from scipy.stats import ttest_1samp
from statsmodels.stats.multitest import multipletests

S_DVS = ["S1", "S2", "S3", "S4", "S5"]
DEFAULT_WWR_LEVELS = [15, 45, 75]
LINEAR_COEF = np.array([-1.0, 0.0, 1.0])
QUADRATIC_COEF = np.array([1.0, -2.0, 1.0])


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


def _exclude_subjects(df: pd.DataFrame, text: str) -> pd.DataFrame:
    if not text:
        return df
    names = [x.strip() for x in str(text).split(",") if x.strip()]
    if not names or "SubjectID" not in df.columns:
        return df
    sid = df["SubjectID"].astype(str).str.strip()
    return df.loc[~sid.isin(set(names))].copy()


def _parse_levels(text: str) -> list[float]:
    vals = [float(x.strip()) for x in str(text).split(",") if x.strip()]
    if len(vals) != 3:
        raise SystemExit("--wwr-levels must contain exactly 3 comma-separated values, e.g. 15,45,75")
    return vals


def _subject_level_wide(df: pd.DataFrame, dv: str, levels: list[float], split_cols: list[str]) -> pd.DataFrame:
    sub = df.dropna(subset=["SubjectID", "WWR", dv]).copy()
    if sub.empty:
        return pd.DataFrame()

    sub["WWR"] = pd.to_numeric(sub["WWR"], errors="coerce")
    sub = sub[sub["WWR"].isin(levels)].copy()
    if sub.empty:
        return pd.DataFrame()

    grp_cols = ["SubjectID"] + split_cols + ["WWR"]
    agg = sub.groupby(grp_cols, as_index=False)[dv].mean()
    wide = agg.pivot_table(index=["SubjectID"] + split_cols, columns="WWR", values=dv, aggfunc="mean")

    for level in levels:
        if level not in wide.columns:
            wide[level] = np.nan

    wide = wide[levels].reset_index()
    rename_map = {level: f"WWR_{int(level) if float(level).is_integer() else level}" for level in levels}
    return wide.rename(columns=rename_map)


def _contrast_test(mat: np.ndarray, coef: np.ndarray) -> dict[str, float]:
    if mat.ndim != 2 or mat.shape[1] != len(coef):
        return {
            "n_subjects": 0,
            "mean_contrast": np.nan,
            "sd_contrast": np.nan,
            "se_contrast": np.nan,
            "t": np.nan,
            "df": np.nan,
            "p": np.nan,
        }

    score = np.dot(mat, coef)
    score = score[np.isfinite(score)]
    n = int(len(score))
    if n < 2:
        return {
            "n_subjects": n,
            "mean_contrast": float(np.nanmean(score)) if n else np.nan,
            "sd_contrast": np.nan,
            "se_contrast": np.nan,
            "t": np.nan,
            "df": np.nan,
            "p": np.nan,
        }

    tt = ttest_1samp(score, popmean=0.0, nan_policy="omit")
    sd = float(np.std(score, ddof=1)) if n >= 2 else np.nan
    se = float(sd / np.sqrt(n)) if n >= 2 else np.nan
    return {
        "n_subjects": n,
        "mean_contrast": float(np.mean(score)),
        "sd_contrast": sd,
        "se_contrast": se,
        "t": float(tt.statistic) if np.isfinite(tt.statistic) else np.nan,
        "df": float(n - 1),
        "p": float(tt.pvalue) if np.isfinite(tt.pvalue) else np.nan,
    }


def _build_markdown(df: pd.DataFrame, out: Path, split_cols: list[str]) -> None:
    lines: list[str] = []
    lines.append("# Analysis-2 / Task5 — SPSS-style Repeated Measures Polynomial Contrasts")
    lines.append("")
    lines.append("This table approximates SPSS `Analyze → General Linear Model → Repeated Measures` with `WWR levels = 3` and `Contrasts = Polynomial`.")
    lines.append("")
    if split_cols:
        lines.append(f"Split columns: {', '.join(split_cols)}")
        lines.append("")

    if df.empty:
        lines.append("No valid results.")
        out.write_text("\n".join(lines), encoding="utf-8")
        return

    display_cols = split_cols + [
        "DV", "Contrast", "n_subjects", "mean_contrast", "t", "df", "p", "p_adjusted", "Sig"
    ]
    x = df[display_cols].copy()
    for c in ["mean_contrast", "t", "df", "p", "p_adjusted"]:
        x[c] = x[c].map(lambda v: "" if pd.isna(v) else f"{float(v):.4f}")
    lines.append(x.to_markdown(index=False))
    out.write_text("\n".join(lines), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser(
        description="Analysis-2 Task5: SPSS-style repeated-measures polynomial contrasts across 3 WWR levels"
    )
    ap.add_argument("--long-csv", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, default=Path("results/research"))
    ap.add_argument("--wwr-levels", default="15,45,75", help="Exactly 3 comma-separated WWR levels in ascending order")
    ap.add_argument("--dvs", default=",".join(S_DVS), help="Comma-separated dependent variables, default S1,S2,S3,S4,S5")
    ap.add_argument("--split-by", default="", help="Optional comma-separated split columns, e.g. Repetition or ExperienceGroup")
    ap.add_argument("--exclude-subjects", default="", help="Comma-separated SubjectID list for QC exclusion")
    ap.add_argument("--p-adjust", default="holm", help="Multiple-testing adjustment: holm|bonferroni|fdr_bh|none")
    args = ap.parse_args()

    out = args.out_dir
    out.mkdir(parents=True, exist_ok=True)

    levels = _parse_levels(args.wwr_levels)
    dvs = [x.strip() for x in str(args.dvs).split(",") if x.strip()]
    split_cols = [x.strip() for x in str(args.split_by).split(",") if x.strip()]

    df = pd.read_csv(args.long_csv)
    df = _exclude_subjects(df, args.exclude_subjects)

    required = ["SubjectID", "WWR"] + split_cols
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise SystemExit(f"Missing required columns: {missing}")

    rows: list[dict] = []
    wide_exports: list[str] = []

    for dv in dvs:
        if dv not in df.columns:
            continue
        wide = _subject_level_wide(df, dv, levels, split_cols)
        wide_path = out / f"analysis2_task5_subject_means_{dv}.csv"
        wide.to_csv(wide_path, index=False, encoding="utf-8-sig")
        wide_exports.append(str(wide_path.relative_to(out)))

        level_cols = [f"WWR_{int(level) if float(level).is_integer() else level}" for level in levels]
        if wide.empty:
            for contrast_name in ["Linear", "Quadratic"]:
                item = {c: "ALL" for c in split_cols}
                item.update({
                    "DV": dv,
                    "Contrast": contrast_name,
                    "n_subjects": 0,
                    "mean_contrast": np.nan,
                    "sd_contrast": np.nan,
                    "se_contrast": np.nan,
                    "t": np.nan,
                    "df": np.nan,
                    "p": np.nan,
                    "status": "no_data",
                })
                rows.append(item)
            continue

        grouped = wide.groupby(split_cols, dropna=False) if split_cols else [((), wide)]
        for key, g in grouped:
            block = g.dropna(subset=level_cols, how="any").copy()
            mat = block[level_cols].to_numpy(dtype=float) if not block.empty else np.empty((0, 3))
            split_values = {}
            if split_cols:
                if not isinstance(key, tuple):
                    key = (key,)
                split_values = dict(zip(split_cols, key))
            else:
                split_values = {}

            linear = _contrast_test(mat, LINEAR_COEF)
            quadratic = _contrast_test(mat, QUADRATIC_COEF)
            for contrast_name, stat in [("Linear", linear), ("Quadratic", quadratic)]:
                item = dict(split_values)
                item.update({
                    "DV": dv,
                    "Contrast": contrast_name,
                    **stat,
                    "status": "ok" if stat["n_subjects"] >= 2 else "insufficient_complete_subjects",
                })
                rows.append(item)

    res = pd.DataFrame(rows)
    if not res.empty:
        if args.p_adjust.lower() == "none":
            res["p_adjusted"] = res["p"]
        else:
            mask = res["p"].notna()
            res["p_adjusted"] = np.nan
            if mask.any():
                _, padj, _, _ = multipletests(res.loc[mask, "p"].astype(float), method=args.p_adjust)
                res.loc[mask, "p_adjusted"] = padj
        res["Sig"] = res["p_adjusted"].map(_sigstar)
        order_cols = split_cols + ["DV", "Contrast", "n_subjects", "mean_contrast", "sd_contrast", "se_contrast", "t", "df", "p", "p_adjusted", "Sig", "status"]
        res = res[order_cols].sort_values(split_cols + ["DV", "Contrast"] if split_cols else ["DV", "Contrast"]).reset_index(drop=True)

    csv_path = out / "analysis2_task5_spss_polynomial_contrasts.csv"
    md_path = out / "analysis2_task5_spss_polynomial_contrasts.md"
    summary_path = out / "analysis2_task5_spss_polynomial_summary.json"
    res.to_csv(csv_path, index=False, encoding="utf-8-sig")
    _build_markdown(res, md_path, split_cols)

    payload = {
        "task": "analysis-2/task5 spss-style repeated-measures polynomial contrasts",
        "dvs": dvs,
        "wwr_levels": levels,
        "split_by": split_cols,
        "contrast_coefficients": {
            "Linear": LINEAR_COEF.tolist(),
            "Quadratic": QUADRATIC_COEF.tolist(),
        },
        "outputs": [
            str(csv_path.relative_to(out)),
            str(md_path.relative_to(out)),
            *wide_exports,
        ],
        "notes": [
            "Subject-level means are computed within each WWR level before contrast testing.",
            "For 3 WWR levels, Linear uses [-1, 0, 1] and Quadratic uses [1, -2, 1].",
            "This is intended to align with the SPSS Within-Subjects Polynomial Contrasts use case.",
        ],
    }
    summary_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False))


if __name__ == "__main__":
    main()
