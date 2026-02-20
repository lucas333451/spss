#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import argparse
import json
import numpy as np
import pandas as pd


def _fmt(x):
    if pd.isna(x):
        return "NA"
    return f"{x:.3f}"


def build_summary(long_csv: Path, research_dir: Path) -> str:
    df = pd.read_csv(long_csv)
    for c in ["WWR", "Complexity", "Repetition"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")

    if "ExperienceGroup" not in df.columns:
        df["ExperienceGroup"] = "Unknown"
    if "SportFreqGroup" not in df.columns:
        df["SportFreqGroup"] = "Unknown"
    if "Repetition" not in df.columns:
        df["Repetition"] = df["Block"] if "Block" in df.columns else np.nan

    df["PeopleGroup4"] = df["ExperienceGroup"].astype(str) + "__" + df["SportFreqGroup"].astype(str)

    dvs_main = [c for c in ["S1", "S2", "S3", "S4"] if c in df.columns]
    dvs_supp = [c for c in ["S5"] if c in df.columns]
    dvs = dvs_main + dvs_supp

    lines = []
    lines.append("# Narrative Summary (Angles 1 & 2)")
    lines.append("")
    lines.append("## Angle 1: WWR × Complexity + frequency sensitivity")
    lines.append("核心问题（主构念）：WWR(3) × Complexity(2) 是否影响 S1~S4（感知可供性），且这种关系是否因频率组而异。")
    lines.append("补充问题：S5（情感体验，1-9）单独报告，不并入 S1~S4。")
    lines.append("")

    # C1 vs C0 drop by group
    if "Complexity" in df.columns and not df.empty:
        rows = []
        for dv in dvs:
            sub = df.dropna(subset=[dv, "Complexity", "PeopleGroup4"]).copy()
            if sub.empty:
                continue
            grp = sub.groupby(["PeopleGroup4", "Complexity"], dropna=False)[dv].mean().reset_index()
            piv = grp.pivot_table(index="PeopleGroup4", columns="Complexity", values=dv, aggfunc="mean")
            if 0 in piv.columns and 1 in piv.columns:
                piv = piv.reset_index()
                piv["DV"] = dv
                piv["C1_minus_C0"] = piv[1] - piv[0]
                rows.append(piv[["DV", "PeopleGroup4", 0, 1, "C1_minus_C0"]])
        if rows:
            drop_df = pd.concat(rows, ignore_index=True)
            drop_df = drop_df.rename(columns={0: "mean_C0", 1: "mean_C1"})
            drop_df.to_csv(research_dir / "angle1_c1_minus_c0_by_group.csv", index=False, encoding="utf-8-sig")

            lines.append("各人群在高复杂度(C1)相对低复杂度(C0)的变化（C1-C0，负值=下降）：")
            lines.append("")
            for dv in dvs:
                s = drop_df[drop_df["DV"] == dv].sort_values("C1_minus_C0")
                if s.empty:
                    continue
                lines.append(f"- {dv}:")
                for _, r in s.iterrows():
                    lines.append(f"  - {r['PeopleGroup4']}: C0={_fmt(r['mean_C0'])}, C1={_fmt(r['mean_C1'])}, Δ={_fmt(r['C1_minus_C0'])}")
            lines.append("")

            # quick verdict: all groups lower?
            verdict = []
            for dv in dvs:
                s = drop_df[drop_df["DV"] == dv]
                if s.empty:
                    continue
                all_lower = bool((s["C1_minus_C0"] < 0).all())
                span = s["C1_minus_C0"].max() - s["C1_minus_C0"].min() if len(s) >= 2 else np.nan
                verdict.append((dv, all_lower, span))
            lines.append("快速判断：")
            for dv, all_lower, span in verdict:
                tag = "各组普遍下降" if all_lower else "并非所有组都下降"
                lines.append(f"- {dv}: {tag}；组间降幅差(最大-最小)={_fmt(span)}")
            lines.append("")

    lines.append("## Angle 2: Round effect (convergence/habituation)")
    lines.append("核心问题：Round1→Round2 是否出现收敛/学习，以及是否存在频率组差异。")
    lines.append("")

    if all((c in df.columns for c in ["SubjectID", "SceneID", "Repetition", "SportFreqGroup"])):
        rd_rows = []
        for dv in dvs:
            sub = df.dropna(subset=["SubjectID", "SceneID", "Repetition", "SportFreqGroup", dv]).copy()
            piv = sub.pivot_table(index=["SubjectID", "SceneID", "SportFreqGroup", "PeopleGroup4"], columns="Repetition", values=dv, aggfunc="mean").reset_index()
            if 1 in piv.columns and 2 in piv.columns:
                piv["diff_r2_minus_r1"] = piv[2] - piv[1]
                g = piv.groupby("PeopleGroup4", dropna=False)["diff_r2_minus_r1"].agg(["count", "mean", "std"]).reset_index()
                g["DV"] = dv
                rd_rows.append(g)
        if rd_rows:
            rd = pd.concat(rd_rows, ignore_index=True)
            rd.to_csv(research_dir / "angle2_round_diff_by_group.csv", index=False, encoding="utf-8-sig")
            lines.append("各人群 Round2-Round1（负值=第二遍更低）:")
            for dv in dvs:
                s = rd[rd["DV"] == dv]
                if s.empty:
                    continue
                lines.append(f"- {dv}:")
                for _, r in s.iterrows():
                    lines.append(f"  - {r['PeopleGroup4']}: n={int(r['count'])}, mean={_fmt(r['mean'])}, sd={_fmt(r['std'])}")
            lines.append("")

    lines.append("## Key output files to inspect")
    lines.append("- group_complexity_mean_table.csv (每个DV的人群×复杂度二维均值表)")
    lines.append("- group_complexity_delta_significance.csv (组间复杂度差异显著性，比较各组 C1-C0 的差值)")
    lines.append("- group_complexity_mean_table_by_wwr.csv / group_complexity_delta_significance_by_wwr.csv (按WWR分层)")
    lines.append("- group_complexity_delta_by_round.csv / group_complexity_delta_round_shift.csv (按轮次细分，检验顺序效应)")
    lines.append("- figures/group_complexity_heatmap_S*.png (人群×复杂度均值热图)")
    lines.append("- figures/group_complexity_delta_S*.png (各人群 C1-C0 横向条形图)")
    lines.append("- group_comparisons_item_level.csv (S题四类人群比较)")
    lines.append("- b_items_group_comparisons.csv (B题四类人群比较)")
    lines.append("- angle1_c1_minus_c0_by_group.csv (直接回答‘高复杂度是否普遍下降/降幅是否不同’)")
    lines.append("- angle2_round_diff_by_group.csv (重复两遍收敛/学习)")
    lines.append("- round_icc_by_group.csv (各人群Round一致性 ICC(A,1))")
    lines.append("")

    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="Build narrative summary for angles 1 & 2")
    ap.add_argument("--long-csv", type=Path, required=True)
    ap.add_argument("--research-dir", type=Path, default=Path("results/research"))
    ap.add_argument("--out", type=Path, default=Path("results/research/analysis_narrative.md"))
    args = ap.parse_args()

    args.research_dir.mkdir(parents=True, exist_ok=True)
    text = build_summary(args.long_csv, args.research_dir)
    args.out.write_text(text, encoding="utf-8")
    print(json.dumps({"out": str(args.out)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
