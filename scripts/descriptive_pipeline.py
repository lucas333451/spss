#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import argparse
import json

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from scipy.stats import skew, kurtosis, shapiro, sem, t

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


def _ci95(z: pd.Series) -> tuple[float, float]:
    zz = pd.to_numeric(z, errors="coerce").dropna()
    n = int(len(zz))
    if n < 2:
        return np.nan, np.nan
    m = float(zz.mean())
    se = float(sem(zz, nan_policy="omit"))
    h = float(t.ppf(0.975, df=n - 1) * se)
    return m - h, m + h


def _norm_p(z: pd.Series) -> float:
    zz = pd.to_numeric(z, errors="coerce").dropna()
    if len(zz) < 3 or len(zz) > 5000:
        return np.nan
    try:
        return float(shapiro(zz).pvalue)
    except Exception:
        return np.nan


def _desc_table(df: pd.DataFrame, cols: list[str], group_cols: list[str] | None = None) -> pd.DataFrame:
    rows = []
    use_cols = [c for c in cols if c in df.columns]
    if not use_cols:
        return pd.DataFrame()

    group_cols = group_cols or []
    if group_cols:
        grouped = df.groupby(group_cols, dropna=False)
        iter_items = list(grouped)
    else:
        iter_items = [((), df.copy())]

    for key, sub in iter_items:
        if not isinstance(key, tuple):
            key = (key,)
        key_map = dict(zip(group_cols, key)) if group_cols else {"Group": "ALL"}
        for c in use_cols:
            z = pd.to_numeric(sub[c], errors="coerce")
            n = int(z.notna().sum())
            ci_low, ci_high = _ci95(z)
            rows.append({
                **key_map,
                "DV": c,
                "n": n,
                "mean": float(z.mean()) if n else np.nan,
                "sd": float(z.std(ddof=1)) if n > 1 else np.nan,
                "median": float(z.median()) if n else np.nan,
                "min": float(z.min()) if n else np.nan,
                "max": float(z.max()) if n else np.nan,
                "skewness": float(skew(z.dropna(), bias=False)) if n > 2 else np.nan,
                "kurtosis": float(kurtosis(z.dropna(), fisher=True, bias=False)) if n > 3 else np.nan,
                "ci95_low": ci_low,
                "ci95_high": ci_high,
                "shapiro_p": _norm_p(z),
            })
    return pd.DataFrame(rows)


def _subject_level_ipq(df: pd.DataFrame) -> pd.DataFrame:
    if "SubjectID" not in df.columns:
        return df.copy()
    return df.groupby("SubjectID", as_index=False).first()


def _plot_distribution_panels(df: pd.DataFrame, cols: list[str], out_dir: Path, prefix: str, hue: str | None = None, xcol: str | None = None) -> list[str]:
    made = []
    use_cols = [c for c in cols if c in df.columns]
    if not use_cols:
        return made
    out_dir.mkdir(parents=True, exist_ok=True)

    for dv in use_cols:
        sub = df.dropna(subset=[dv]).copy()
        if sub.empty:
            continue

        # violin
        plt.figure(figsize=(6.2, 4.4))
        if xcol and xcol in sub.columns:
            sns.violinplot(data=sub, x=xcol, y=dv, hue=hue if hue in sub.columns else None, inner="box", cut=0)
        else:
            sns.violinplot(data=sub, y=dv, inner="box", cut=0, color="#8EC5B6")
        plt.title(f"{dv} violin")
        plt.tight_layout()
        p1 = out_dir / f"{prefix}_{dv}_violin.png"
        plt.savefig(p1, dpi=230)
        plt.close()
        made.append(str(p1))

        # box
        plt.figure(figsize=(6.2, 4.4))
        if xcol and xcol in sub.columns:
            sns.boxplot(data=sub, x=xcol, y=dv, hue=hue if hue in sub.columns else None)
        else:
            sns.boxplot(data=sub, y=dv, color="#A8D5C8")
        plt.title(f"{dv} boxplot")
        plt.tight_layout()
        p2 = out_dir / f"{prefix}_{dv}_box.png"
        plt.savefig(p2, dpi=230)
        plt.close()
        made.append(str(p2))
    return made


def main():
    ap = argparse.ArgumentParser(description="Descriptive-only pipeline: overall + experience")
    ap.add_argument("--long-csv", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, default=Path("results/descriptive"))
    ap.add_argument("--with-qc", action="store_true", help="Also export QC-excluded outputs")
    args = ap.parse_args()

    apply_bae_style()

    out = args.out_dir
    out.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(args.long_csv)

    branches = [("raw", "")]
    if args.with_qc:
        branches.append(("qc", QC_EXCLUDE))

    outputs: list[str] = []

    for branch, exclude in branches:
        base = out / branch
        base.mkdir(parents=True, exist_ok=True)
        x = _exclude_subjects(df, exclude)

        # overall
        overall_dir = base / "overall"
        overall_dir.mkdir(parents=True, exist_ok=True)
        fig_dir_overall = overall_dir / "figures"

        s_overall = _desc_table(x, S_COLS)
        s_overall_wwr = _desc_table(x, S_COLS, ["WWR"]) if "WWR" in x.columns else pd.DataFrame()
        s_overall_cx = _desc_table(x, S_COLS, ["Complexity"]) if "Complexity" in x.columns else pd.DataFrame()

        b_src = x[x["Complexity"].astype(str).isin(["1", "1.0"])].copy() if "Complexity" in x.columns else x
        b_overall = _desc_table(b_src, B_COLS)
        b_overall_wwr = _desc_table(b_src, B_COLS, ["WWR"]) if "WWR" in b_src.columns else pd.DataFrame()

        ipq_subj = _subject_level_ipq(x)
        ipq_overall = _desc_table(ipq_subj, IPQ_COLS)

        s_overall.to_csv(overall_dir / "s1_s5_descriptives.csv", index=False, encoding="utf-8-sig")
        s_overall_wwr.to_csv(overall_dir / "s1_s5_descriptives_by_wwr.csv", index=False, encoding="utf-8-sig")
        s_overall_cx.to_csv(overall_dir / "s1_s5_descriptives_by_complexity.csv", index=False, encoding="utf-8-sig")
        b_overall.to_csv(overall_dir / "b1_b3_descriptives.csv", index=False, encoding="utf-8-sig")
        b_overall_wwr.to_csv(overall_dir / "b1_b3_descriptives_by_wwr.csv", index=False, encoding="utf-8-sig")
        ipq_overall.to_csv(overall_dir / "ipq_descriptives.csv", index=False, encoding="utf-8-sig")

        outputs += [
            str((overall_dir / "s1_s5_descriptives.csv").relative_to(out)),
            str((overall_dir / "s1_s5_descriptives_by_wwr.csv").relative_to(out)),
            str((overall_dir / "s1_s5_descriptives_by_complexity.csv").relative_to(out)),
            str((overall_dir / "b1_b3_descriptives.csv").relative_to(out)),
            str((overall_dir / "b1_b3_descriptives_by_wwr.csv").relative_to(out)),
            str((overall_dir / "ipq_descriptives.csv").relative_to(out)),
        ]

        for p in _plot_distribution_panels(x, S_COLS, fig_dir_overall, prefix="overall_s", xcol="WWR" if "WWR" in x.columns else None):
            outputs.append(str(Path(p).relative_to(out)))
        for p in _plot_distribution_panels(b_src, B_COLS, fig_dir_overall, prefix="overall_b", xcol="WWR" if "WWR" in b_src.columns else None):
            outputs.append(str(Path(p).relative_to(out)))

        # experience
        if "ExperienceGroup" in x.columns:
            exp_dir = base / "experience"
            exp_dir.mkdir(parents=True, exist_ok=True)
            fig_dir_exp = exp_dir / "figures"

            s_exp = _desc_table(x, S_COLS, ["ExperienceGroup"])
            s_exp_wwr = _desc_table(x, S_COLS, ["ExperienceGroup", "WWR"]) if "WWR" in x.columns else pd.DataFrame()
            s_exp_cx = _desc_table(x, S_COLS, ["ExperienceGroup", "Complexity"]) if "Complexity" in x.columns else pd.DataFrame()

            b_exp = _desc_table(b_src, B_COLS, ["ExperienceGroup"])
            b_exp_wwr = _desc_table(b_src, B_COLS, ["ExperienceGroup", "WWR"]) if "WWR" in b_src.columns else pd.DataFrame()

            ipq_exp = _desc_table(ipq_subj, IPQ_COLS, ["ExperienceGroup"])

            s_exp.to_csv(exp_dir / "s1_s5_descriptives_by_experience.csv", index=False, encoding="utf-8-sig")
            s_exp_wwr.to_csv(exp_dir / "s1_s5_descriptives_by_experience_wwr.csv", index=False, encoding="utf-8-sig")
            s_exp_cx.to_csv(exp_dir / "s1_s5_descriptives_by_experience_complexity.csv", index=False, encoding="utf-8-sig")
            b_exp.to_csv(exp_dir / "b1_b3_descriptives_by_experience.csv", index=False, encoding="utf-8-sig")
            b_exp_wwr.to_csv(exp_dir / "b1_b3_descriptives_by_experience_wwr.csv", index=False, encoding="utf-8-sig")
            ipq_exp.to_csv(exp_dir / "ipq_descriptives_by_experience.csv", index=False, encoding="utf-8-sig")

            outputs += [
                str((exp_dir / "s1_s5_descriptives_by_experience.csv").relative_to(out)),
                str((exp_dir / "s1_s5_descriptives_by_experience_wwr.csv").relative_to(out)),
                str((exp_dir / "s1_s5_descriptives_by_experience_complexity.csv").relative_to(out)),
                str((exp_dir / "b1_b3_descriptives_by_experience.csv").relative_to(out)),
                str((exp_dir / "b1_b3_descriptives_by_experience_wwr.csv").relative_to(out)),
                str((exp_dir / "ipq_descriptives_by_experience.csv").relative_to(out)),
            ]

            for p in _plot_distribution_panels(x, S_COLS, fig_dir_exp, prefix="experience_s", hue="ExperienceGroup", xcol="WWR" if "WWR" in x.columns else "ExperienceGroup"):
                outputs.append(str(Path(p).relative_to(out)))
            for p in _plot_distribution_panels(b_src, B_COLS, fig_dir_exp, prefix="experience_b", hue="ExperienceGroup", xcol="WWR" if "WWR" in b_src.columns else "ExperienceGroup"):
                outputs.append(str(Path(p).relative_to(out)))

    payload = {
        "task": "descriptive pipeline",
        "scope": ["overall", "experience"],
        "branches": [b for b, _ in branches],
        "outputs": outputs,
        "stats": ["n", "mean", "sd", "median", "min", "max", "skewness", "kurtosis", "ci95", "shapiro_p"],
        "stratification": ["WWR", "Complexity", "ExperienceGroup"],
    }
    (out / "descriptive_summary.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False))


if __name__ == "__main__":
    main()
