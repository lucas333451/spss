#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import argparse
import json

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import warnings
from statsmodels.formula.api import mixedlm, ols
from statsmodels.tools.sm_exceptions import ConvergenceWarning

from analysis_groups import make_people_group4
from plot_style import apply_bae_style

S_DVS = ["S1", "S2", "S3", "S4", "S5"]


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


def _fit_trend(sub: pd.DataFrame):
    # normalized coding: WWR 15/45/75 -> -1/0/1
    d = sub.copy()
    d["w"] = (pd.to_numeric(d["WWR"], errors="coerce") - 45.0) / 30.0
    d["w2"] = d["w"] ** 2
    d = d.dropna(subset=["score", "w", "w2", "SubjectID"])
    if d.empty or d["SubjectID"].nunique() < 3:
        return None

    try:
        with warnings.catch_warnings(record=True) as ws:
            warnings.simplefilter("always")
            fit = mixedlm("score ~ w + w2", data=d, groups=d["SubjectID"]).fit(reml=False, method="lbfgs", maxiter=2000)

        bad_warn = False
        for wmsg in ws:
            txt = str(wmsg.message).lower()
            if ("singular" in txt) or isinstance(wmsg.message, ConvergenceWarning):
                bad_warn = True
                break

        if (not getattr(fit, "converged", True)) or bad_warn:
            raise RuntimeError("mixedlm_singular_or_boundary")

        return {
            "method": "mixedlm",
            "coef_linear": float(fit.params.get("w", np.nan)),
            "p_linear": float(fit.pvalues.get("w", np.nan)),
            "coef_quad": float(fit.params.get("w2", np.nan)),
            "p_quad": float(fit.pvalues.get("w2", np.nan)),
            "aic": float(fit.aic) if pd.notna(fit.aic) else np.nan,
        }
    except Exception:
        # fallback for tiny/unbalanced cells or singular random-effects covariance
        ff = ols("score ~ w + w2 + C(SubjectID)", data=d).fit()
        return {
            "method": "ols_subject_fe",
            "coef_linear": float(ff.params.get("w", np.nan)),
            "p_linear": float(ff.pvalues.get("w", np.nan)),
            "coef_quad": float(ff.params.get("w2", np.nan)),
            "p_quad": float(ff.pvalues.get("w2", np.nan)),
            "aic": float(ff.aic) if pd.notna(ff.aic) else np.nan,
        }


def _plot_trend_lines(means: pd.DataFrame, group_col: str, fig_dir: Path) -> list[str]:
    made = []
    if means.empty:
        return made

    for dv in S_DVS:
        x = means[means["DV"] == dv].copy()
        if x.empty:
            continue

        fig, axes = plt.subplots(1, 2, figsize=(11, 4.2), sharey=True)
        for i, r in enumerate(sorted(x["Repetition"].dropna().unique())):
            ax = axes[i]
            sub = x[x["Repetition"] == r].copy()
            for g, dg in sub.groupby("Group", dropna=False):
                dg = dg.sort_values("WWR")
                ax.plot(dg["WWR"], dg["mean"], marker="o", linewidth=2, label=str(g))
                ax.fill_between(dg["WWR"], dg["mean"] - dg["se"], dg["mean"] + dg["se"], alpha=0.15)
            ax.set_title(f"Round {int(r)}")
            ax.set_xlabel("WWR")
            ax.grid(alpha=0.2)
        axes[0].set_ylabel(dv)
        handles, labels = axes[0].get_legend_handles_labels()
        if handles:
            fig.legend(handles, labels, title=group_col, loc="upper center", ncol=max(1, len(labels)))
        fig.suptitle(f"Task3 WWR trend by round/group: {dv}")
        fig.tight_layout(rect=[0, 0, 1, 0.92])

        p = fig_dir / f"task3_wwr_trend_{dv}.png"
        p.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(p, dpi=230)
        plt.close(fig)
        made.append(str(p))

    return made


def _plot_p_heatmap(models: pd.DataFrame, out_png: Path, p_col: str, title: str) -> bool:
    if models.empty:
        return False
    x = models.copy()
    x["Cell"] = x["DV"].astype(str) + " | R" + x["Repetition"].astype(str)
    mat = x.pivot_table(index="Group", columns="Cell", values=p_col, aggfunc="first")
    if mat.empty:
        return False
    annot = mat.copy().astype(object)
    for r in annot.index:
        for c in annot.columns:
            p = annot.loc[r, c]
            annot.loc[r, c] = "" if pd.isna(p) else f"p={float(p):.4g}{_sigstar(float(p))}"

    plt.figure(figsize=(max(8, 0.65 * len(mat.columns) + 2), max(2.8, 0.52 * len(mat.index) + 1.4)))
    sns.heatmap(
        -np.log10(mat.astype(float)),
        cmap="Blues",
        annot=annot,
        fmt="",
        linewidths=0.6,
        linecolor="#efefef",
        cbar_kws={"label": "-log10(p)"},
    )
    plt.title(title)
    plt.xlabel("DV | Round")
    plt.ylabel("Group")
    plt.tight_layout()
    out_png.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_png, dpi=230)
    plt.close()
    return True


def main():
    ap = argparse.ArgumentParser(description="Analysis-2 Task3: WWR trend (linear/quadratic) for S1-S5 by round and group")
    ap.add_argument("--long-csv", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, default=Path("results/research"))
    ap.add_argument("--group-col", default="PeopleGroup4")
    ap.add_argument("--exclude-subjects", default="", help="Comma-separated SubjectID list for QC exclusion")
    args = ap.parse_args()

    apply_bae_style()

    out = args.out_dir
    out.mkdir(parents=True, exist_ok=True)
    fig_dir = out / "task3_wwr_trend_figures"
    fig_dir.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(args.long_csv)
    df = _exclude_subjects(df, args.exclude_subjects)

    for c in ["SubjectID", "WWR", "Repetition"]:
        if c not in df.columns:
            raise SystemExit(f"Missing required column: {c}")

    if args.group_col == "PeopleGroup4" and "PeopleGroup4" not in df.columns:
        df = make_people_group4(df)
    if args.group_col not in df.columns:
        raise SystemExit(f"Missing group column: {args.group_col}")

    df["Repetition"] = pd.to_numeric(df["Repetition"], errors="coerce")
    df["WWR"] = pd.to_numeric(df["WWR"], errors="coerce")

    rows = []
    mean_rows = []

    for dv in S_DVS:
        if dv not in df.columns:
            continue
        sub0 = df.dropna(subset=["SubjectID", args.group_col, "Repetition", "WWR", dv]).copy()
        if sub0.empty:
            continue

        # subject-level means at each WWR within round/group
        subj = (
            sub0.groupby(["SubjectID", args.group_col, "Repetition", "WWR"], as_index=False)[dv]
            .mean()
            .rename(columns={dv: "score", args.group_col: "Group"})
        )

        # means for plotting
        m = (
            subj.groupby(["Group", "Repetition", "WWR"], as_index=False)
            .agg(mean=("score", "mean"), std=("score", "std"), n=("score", "count"))
        )
        m["se"] = m["std"] / np.sqrt(m["n"].clip(lower=1))
        m["DV"] = dv
        mean_rows.append(m)

        for (g, r), sg in subj.groupby(["Group", "Repetition"], dropna=False):
            fit = _fit_trend(sg)
            if fit is None:
                rows.append({
                    "DV": dv,
                    "Group": g,
                    "Repetition": r,
                    "n_rows": int(len(sg)),
                    "n_subjects": int(sg["SubjectID"].nunique()),
                    "status": "skipped_insufficient_data",
                })
                continue
            rows.append({
                "DV": dv,
                "Group": g,
                "Repetition": r,
                "n_rows": int(len(sg)),
                "n_subjects": int(sg["SubjectID"].nunique()),
                "status": "ok",
                **fit,
            })

    models = pd.DataFrame(rows)
    means = pd.concat(mean_rows, ignore_index=True) if mean_rows else pd.DataFrame()

    models_path = out / "analysis2_task3_wwr_trend_models.csv"
    means_path = out / "analysis2_task3_wwr_trend_means.csv"
    models.to_csv(models_path, index=False, encoding="utf-8-sig")
    means.to_csv(means_path, index=False, encoding="utf-8-sig")

    outputs = [str(models_path.relative_to(out)), str(means_path.relative_to(out))]

    for p in _plot_trend_lines(means, args.group_col, fig_dir):
        outputs.append(str(Path(p).relative_to(out)))

    lin_png = fig_dir / "task3_linear_trend_p_heatmap.png"
    if _plot_p_heatmap(models[models.get("status", "") == "ok"], lin_png, "p_linear", "Task3 linear trend p-values by Group × (DV,Round)"):
        outputs.append(str(lin_png.relative_to(out)))

    quad_png = fig_dir / "task3_quadratic_trend_p_heatmap.png"
    if _plot_p_heatmap(models[models.get("status", "") == "ok"], quad_png, "p_quad", "Task3 quadratic (nonlinear) trend p-values by Group × (DV,Round)"):
        outputs.append(str(quad_png.relative_to(out)))

    payload = {
        "task": "analysis-2/task3 wwr trend",
        "group_col": args.group_col,
        "dvs": [dv for dv in S_DVS if dv in df.columns],
        "outputs": outputs,
        "notes": [
            "Linear trend uses normalized WWR coding (-1,0,1).",
            "Quadratic term tests potential W45 nonlinearity (curvature).",
            "Stratified by round (Repetition) and group.",
        ],
    }
    (out / "analysis2_task3_wwr_trend_summary.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False))


if __name__ == "__main__":
    main()
