#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import argparse
import json
import numpy as np
import pandas as pd

# mapping[Order][Block][Position] = (WWR, Condition)
MAPPING = {
    1: {
        1: {1: (45, "C1"), 2: (15, "C0"), 3: (75, "C1"), 4: (45, "C0"), 5: (15, "C1"), 6: (75, "C0")},
        2: {1: (45, "C0"), 2: (45, "C1"), 3: (75, "C0"), 4: (75, "C1"), 5: (15, "C0"), 6: (15, "C1")},
    },
    2: {
        1: {1: (45, "C1"), 2: (15, "C0"), 3: (75, "C1"), 4: (75, "C0"), 5: (15, "C1"), 6: (45, "C0")},
        2: {1: (15, "C0"), 2: (15, "C1"), 3: (45, "C1"), 4: (75, "C0"), 5: (45, "C0"), 6: (75, "C1")},
    },
}


def q_prefix(block: int, pos: int) -> str:
    if block == 1:
        qn = 1 + pos  # Q2..Q7
    else:
        qn = 8 + pos  # Q9..Q14
    return f"Q{qn}"


def num(v):
    return pd.to_numeric(v, errors="coerce")


def build_long(df: pd.DataFrame, subject_col: str, order_col: str, freq_col: str) -> pd.DataFrame:
    records = []

    for ridx, r in df.reset_index(drop=True).iterrows():
        subject = r.get(subject_col)
        if pd.isna(subject) or str(subject).strip() == "":
            subject = f"SUBJ_{ridx+1:03d}"

        order = int(num(r.get(order_col))) if not pd.isna(num(r.get(order_col))) else np.nan
        sport_freq = r.get(freq_col)

        for block in [1, 2]:
            bvals = None
            if block == 1:
                bvals = [num(r.get("Q8.1_B1. 出现功能性器材要素的场景整体给我一种信息更为丰富的感觉。_")),
                         num(r.get("Q8.2_B2.这些功能性器材要素有助于我理解这个空间如何进行乒乓球活动。_")),
                         num(r.get("Q8.3_B3. 即便出现这些功能性器材要素，这个空间整体看起来仍然是有序的。_"))]
            else:
                bvals = [num(r.get("Q15.1_B1. 出现功能性器材要素的场景整体给我一种信息更为丰富的感觉。_")),
                         num(r.get("Q15.2_B2.这些功能性器材要素有助于我理解这个空间如何进行乒乓球活动。_")),
                         num(r.get("Q15.3_B3. 即便出现这些功能性器材要素，这个空间整体看起来仍然是有序的。_"))]

            for pos in [1, 2, 3, 4, 5, 6]:
                wwr, cond = (np.nan, None)
                if order in MAPPING and block in MAPPING[order] and pos in MAPPING[order][block]:
                    wwr, cond = MAPPING[order][block][pos]

                prefix = q_prefix(block, pos)
                s1 = num(r.get(f"{prefix}.1_S1. 这个空间整体上适合打乒乓球。_"))
                s2 = num(r.get(f"{prefix}.2_S2. 在这个空间里，我比较容易判断自己该站在哪里、怎么走动。_"))
                s3 = num(r.get(f"{prefix}.3_S3. 看这个空间的时候，我能把注意力主要放在球桌区域。_"))
                s4 = num(r.get(f"{prefix}.4_S4. 如果在现实中，我愿意使用这样的乒乓球空间。_"))
                s5 = num(r.get(f"{prefix}.5_S5.愉悦度评价_"))

                if cond == "C1":
                    b1, b2, b3 = bvals
                else:
                    b1, b2, b3 = np.nan, np.nan, np.nan

                afford4 = np.nanmean([s1, s2, s3, s4])
                afford5 = np.nanmean([s1, s2, s3, s4, s5])
                bmean = np.nanmean([b1, b2, b3])
                complexity = 1 if cond == "C1" else 0 if cond == "C0" else np.nan

                records.append({
                    "SubjectID": subject,
                    "Order": order,
                    "Block": block,
                    "Position": pos,
                    "WWR": wwr,
                    "Condition": cond,
                    "Complexity": complexity,
                    "SportFreq": sport_freq,
                    "S1": s1,
                    "S2": s2,
                    "S3": s3,
                    "S4": s4,
                    "S5": s5,
                    "Afford4": afford4,
                    "Afford5": afford5,
                    "Pleasure": s5,
                    "B1": b1,
                    "B2": b2,
                    "B3": b3,
                    "Bmean": bmean,
                    "SceneID": f"WWR{int(wwr)}_{cond}" if not pd.isna(wwr) and cond else np.nan,
                })

    out = pd.DataFrame(records)
    return out


def run_qc(long_df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    issues = []

    # Global checks
    n_subj = long_df["SubjectID"].nunique()
    expected_rows = n_subj * 12
    if len(long_df) != expected_rows:
        issues.append({"SubjectID": "__GLOBAL__", "check": "rows_total", "ok": False,
                       "detail": f"rows={len(long_df)} expected={expected_rows}"})

    # Missing report
    miss = long_df.isna().mean().reset_index()
    miss.columns = ["column", "missing_rate"]

    for sid, g in long_df.groupby("SubjectID"):
        ok = True
        if len(g) != 12:
            ok = False
            issues.append({"SubjectID": sid, "check": "rows_per_subject", "ok": False, "detail": f"{len(g)} != 12"})

        for block in [1, 2]:
            gb = g[g["Block"] == block]
            if len(gb) != 6:
                ok = False
                issues.append({"SubjectID": sid, "check": f"block{block}_rows", "ok": False, "detail": f"{len(gb)} != 6"})
                continue

            c_counts = gb["Condition"].value_counts(dropna=False).to_dict()
            if c_counts.get("C1", 0) != 3 or c_counts.get("C0", 0) != 3:
                ok = False
                issues.append({"SubjectID": sid, "check": f"block{block}_condition_balance", "ok": False,
                               "detail": f"C1={c_counts.get('C1',0)}, C0={c_counts.get('C0',0)}"})

            w_counts = gb["WWR"].value_counts(dropna=False).to_dict()
            if w_counts.get(15, 0) != 2 or w_counts.get(45, 0) != 2 or w_counts.get(75, 0) != 2:
                ok = False
                issues.append({"SubjectID": sid, "check": f"block{block}_wwr_balance", "ok": False,
                               "detail": f"{w_counts}"})

            c0_has_b = gb[(gb["Condition"] == "C0") & (gb[["B1", "B2", "B3"]].notna().any(axis=1))]
            if not c0_has_b.empty:
                ok = False
                issues.append({"SubjectID": sid, "check": f"block{block}_c0_b_should_na", "ok": False,
                               "detail": f"rows={len(c0_has_b)}"})

            c1_missing_b = gb[(gb["Condition"] == "C1") & (gb[["B1", "B2", "B3"]].isna().any(axis=1))]
            if not c1_missing_b.empty:
                ok = False
                issues.append({"SubjectID": sid, "check": f"block{block}_c1_b_should_present", "ok": False,
                               "detail": f"rows={len(c1_missing_b)}"})

            # C1 rows share same B values by design
            c1 = gb[gb["Condition"] == "C1"]
            if len(c1) == 3:
                for bcol in ["B1", "B2", "B3"]:
                    if c1[bcol].nunique(dropna=True) > 1:
                        ok = False
                        issues.append({"SubjectID": sid, "check": f"block{block}_{bcol}_consistent", "ok": False,
                                       "detail": "C1 rows do not share identical value"})

        if ok:
            issues.append({"SubjectID": sid, "check": "all", "ok": True, "detail": "pass"})

    issue_df = pd.DataFrame(issues)
    abnormal = issue_df[(issue_df["ok"] == False) & (issue_df["SubjectID"] != "__GLOBAL__")]["SubjectID"].drop_duplicates()
    summary = {
        "n_subjects": int(n_subj),
        "total_rows": int(len(long_df)),
        "expected_rows": int(expected_rows),
        "n_abnormal_subjects": int(abnormal.nunique()),
        "abnormal_subjects": abnormal.tolist(),
        "qc_pass": bool((issue_df["ok"] == False).sum() == 0),
    }
    return issue_df, miss, summary


def main():
    ap = argparse.ArgumentParser(description="Convert wide questionnaire Excel to long-format for LMM")
    ap.add_argument("--excel", type=Path, required=True)
    ap.add_argument("--sheet", default=0)
    ap.add_argument("--subject-col", default="姓名")
    ap.add_argument("--order-col", default="Q1.8_场景顺序编号")
    ap.add_argument("--freq-col", default="Q1.5_近 6 个月平均运动频率：")
    ap.add_argument("--out-dir", type=Path, default=Path("results/long"))
    args = ap.parse_args()

    out = args.out_dir
    out.mkdir(parents=True, exist_ok=True)

    df = pd.read_excel(args.excel, sheet_name=args.sheet)
    long_df = build_long(df, args.subject_col, args.order_col, args.freq_col)
    qc_df, miss_df, qc_summary = run_qc(long_df)

    long_df.to_csv(out / "long_format.csv", index=False, encoding="utf-8-sig")
    qc_df.to_csv(out / "qc_issues.csv", index=False, encoding="utf-8-sig")
    miss_df.to_csv(out / "missing_rate.csv", index=False, encoding="utf-8-sig")
    (out / "qc_summary.json").write_text(json.dumps(qc_summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(qc_summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
