#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import argparse
import json
import re
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


def q_num(block: int, pos: int) -> int:
    return (1 + pos) if block == 1 else (8 + pos)  # block1: Q2..Q7; block2: Q9..Q14


def detect_format(columns: list[str]) -> str:
    cols = set(columns)
    if {"name", "Q1.8", "Q2.1_1"}.issubset(cols):
        return "coded"
    return "text"


def to_num(v):
    if pd.isna(v):
        return np.nan
    if isinstance(v, (int, float, np.number)):
        return float(v)
    s = str(v).strip()
    if s == "":
        return np.nan
    # 兼容“6分”“7 分”等文本评分
    m = re.search(r"-?\d+(?:\.\d+)?", s)
    if m:
        try:
            return float(m.group(0))
        except Exception:
            return np.nan
    return np.nan


def find_first_col(columns: list[str], *, prefix: str | None = None, contains: str | None = None, fallback: str | None = None) -> str | None:
    if fallback and fallback in columns:
        return fallback
    for c in columns:
        if prefix is not None and not c.startswith(prefix):
            continue
        if contains is not None and contains not in c:
            continue
        return c
    return None


def split_experience_group(v) -> str:
    x = to_num(v)
    if pd.isna(x):
        return "Unknown"
    # Lucas规则：Q1.4 前低后高（1=Low；2/3/4=High）
    return "Low" if int(x) == 1 else "High"


def split_sport_freq_group(v) -> str:
    x = to_num(v)
    if pd.isna(x):
        return "Unknown"
    # Lucas规则：Q1.5 选4=高频；选1/2/3=低频
    return "High" if int(x) == 4 else "Low"


def build_column_index(df: pd.DataFrame, mode: str, subject_col: str | None, order_col: str | None, freq_col: str | None) -> dict:
    cols = [str(c) for c in df.columns]
    idx: dict[str, str] = {}

    if mode == "coded":
        idx["subject"] = subject_col or "name"
        idx["order"] = order_col or "Q1.8"
        idx["freq"] = freq_col or "Q1.5"
        idx["exp"] = "Q1.4"

        for block in [1, 2]:
            for pos in [1, 2, 3, 4, 5, 6]:
                qn = q_num(block, pos)
                for i in [1, 2, 3, 4, 5]:
                    key = f"S_{block}_{pos}_{i}"
                    idx[key] = f"Q{qn}.{i}_1"

            bq = 8 if block == 1 else 15
            for i in [1, 2, 3]:
                idx[f"B_{block}_{i}"] = f"Q{bq}.{i}_1"

    else:  # text
        idx["subject"] = subject_col or find_first_col(cols, fallback="姓名", prefix="姓名")
        idx["order"] = order_col or find_first_col(cols, fallback="Q1.8_场景顺序编号", prefix="Q1.8")
        idx["freq"] = freq_col or find_first_col(cols, fallback="Q1.5_近 6 个月平均运动频率：", prefix="Q1.5")
        idx["exp"] = find_first_col(cols, fallback="Q1.4_乒乓球经验：", prefix="Q1.4")

        for block in [1, 2]:
            for pos in [1, 2, 3, 4, 5, 6]:
                qn = q_num(block, pos)
                for i in [1, 2, 3, 4, 5]:
                    key = f"S_{block}_{pos}_{i}"
                    idx[key] = find_first_col(cols, prefix=f"Q{qn}.{i}_")

            bq = 8 if block == 1 else 15
            for i in [1, 2, 3]:
                idx[f"B_{block}_{i}"] = find_first_col(cols, prefix=f"Q{bq}.{i}_")

    required = ["subject", "order", "freq", "exp"]
    missing_required = [k for k in required if (k not in idx or idx[k] is None or idx[k] not in cols)]
    if missing_required:
        raise ValueError(f"Missing required columns for mode={mode}: {missing_required}. Resolved={{{k: idx.get(k) for k in required}}}")

    return idx


def build_long(df: pd.DataFrame, col_idx: dict) -> pd.DataFrame:
    records = []

    for ridx, r in df.reset_index(drop=True).iterrows():
        subject = r.get(col_idx["subject"])
        if pd.isna(subject) or str(subject).strip() == "":
            subject = f"SUBJ_{ridx+1:03d}"

        order_raw = to_num(r.get(col_idx["order"]))
        order = int(order_raw) if not pd.isna(order_raw) else np.nan
        sport_freq = to_num(r.get(col_idx["freq"]))
        exp_raw = to_num(r.get(col_idx["exp"]))

        exp_group = split_experience_group(exp_raw)
        sport_freq_group = split_sport_freq_group(sport_freq)

        for block in [1, 2]:
            bvals = [
                to_num(r.get(col_idx.get(f"B_{block}_1"))),
                to_num(r.get(col_idx.get(f"B_{block}_2"))),
                to_num(r.get(col_idx.get(f"B_{block}_3"))),
            ]

            for pos in [1, 2, 3, 4, 5, 6]:
                wwr, cond = (np.nan, None)
                if order in MAPPING and block in MAPPING[order] and pos in MAPPING[order][block]:
                    wwr, cond = MAPPING[order][block][pos]

                s1 = to_num(r.get(col_idx.get(f"S_{block}_{pos}_1")))
                s2 = to_num(r.get(col_idx.get(f"S_{block}_{pos}_2")))
                s3 = to_num(r.get(col_idx.get(f"S_{block}_{pos}_3")))
                s4 = to_num(r.get(col_idx.get(f"S_{block}_{pos}_4")))
                s5 = to_num(r.get(col_idx.get(f"S_{block}_{pos}_5")))

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
                    "Repetition": block,
                    "RepetitionC": -0.5 if block == 1 else 0.5,
                    "Position": pos,
                    "WWR": wwr,
                    "Condition": cond,
                    "Complexity": complexity,
                    "SportFreq": sport_freq,
                    "Experience": exp_raw,
                    "ExperienceGroup": exp_group,
                    "SportFreqGroup": sport_freq_group,
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

    return pd.DataFrame(records)


def run_qc(long_df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    issues = []

    n_subj = long_df["SubjectID"].nunique()
    expected_rows = n_subj * 12
    if len(long_df) != expected_rows:
        issues.append({"SubjectID": "__GLOBAL__", "check": "rows_total", "ok": False,
                       "detail": f"rows={len(long_df)} expected={expected_rows}"})

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


def _parse_sheet_arg(sheet_arg):
    """Allow both sheet index and sheet name.

    - "0" / 0 -> int(0)
    - "Sheet1" -> "Sheet1"
    """
    if isinstance(sheet_arg, int):
        return sheet_arg
    s = str(sheet_arg).strip()
    if s.isdigit():
        return int(s)
    return s


def main():
    ap = argparse.ArgumentParser(description="Convert questionnaire Excel (text/coded export) to long-format for LMM")
    ap.add_argument("--excel", type=Path, required=True)
    ap.add_argument("--sheet", default=0, help="Worksheet index (e.g., 0) or worksheet name")
    ap.add_argument("--mode", choices=["auto", "text", "coded"], default="auto")
    ap.add_argument("--subject-col", default=None, help="Optional override of subject column")
    ap.add_argument("--order-col", default=None, help="Optional override of order column")
    ap.add_argument("--freq-col", default=None, help="Optional override of sport-frequency column")
    ap.add_argument("--out-dir", type=Path, default=Path("results/long"))
    args = ap.parse_args()

    out = args.out_dir
    out.mkdir(parents=True, exist_ok=True)

    excel_path = str(args.excel)
    # Tolerate accidental surrounding spaces in path argument (common in copy/paste)
    if not Path(excel_path).exists() and Path(excel_path.strip()).exists():
        excel_path = excel_path.strip()

    sheet = _parse_sheet_arg(args.sheet)
    try:
        df = pd.read_excel(excel_path, sheet_name=sheet)
    except ValueError as e:
        msg = str(e)
        if "Worksheet named" in msg and isinstance(sheet, str) and sheet.isdigit():
            # Defensive fallback for environments where CLI passed "0" as string sheet-name
            df = pd.read_excel(excel_path, sheet_name=int(sheet))
        else:
            raise
    mode = detect_format([str(c) for c in df.columns]) if args.mode == "auto" else args.mode
    col_idx = build_column_index(df, mode, args.subject_col, args.order_col, args.freq_col)

    long_df = build_long(df, col_idx)
    qc_df, miss_df, qc_summary = run_qc(long_df)

    long_df.to_csv(out / "long_format.csv", index=False, encoding="utf-8-sig")
    qc_df.to_csv(out / "qc_issues.csv", index=False, encoding="utf-8-sig")
    miss_df.to_csv(out / "missing_rate.csv", index=False, encoding="utf-8-sig")
    (out / "qc_summary.json").write_text(json.dumps(qc_summary, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "column_resolution.json").write_text(json.dumps({"mode": mode, "columns": col_idx}, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps({"mode": mode, **qc_summary}, ensure_ascii=False))


if __name__ == "__main__":
    main()
