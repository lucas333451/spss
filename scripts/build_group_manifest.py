#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import argparse
import json
import pandas as pd


def build_manifest(long_csv: Path, out_csv: Path) -> pd.DataFrame:
    df = pd.read_csv(long_csv)

    required = ["SubjectID", "SportFreqGroup", "ExperienceGroup"]
    miss = [c for c in required if c not in df.columns]
    if miss:
        raise SystemExit(f"Missing required columns in long CSV: {miss}")

    x = (
        df[["SubjectID", "SportFreqGroup", "ExperienceGroup"]]
        .dropna(subset=["SubjectID"])
        .copy()
    )
    x["SubjectID"] = x["SubjectID"].astype(str).str.strip()
    x = x[x["SubjectID"] != ""]

    rows = []
    for sid, g in x.groupby("SubjectID", dropna=False):
        sport_vals = sorted({str(v) for v in g["SportFreqGroup"].dropna().astype(str)})
        exp_vals = sorted({str(v) for v in g["ExperienceGroup"].dropna().astype(str)})

        sport = sport_vals[0] if len(sport_vals) == 1 else ("Unknown" if len(sport_vals) == 0 else "Inconsistent")
        exp = exp_vals[0] if len(exp_vals) == 1 else ("Unknown" if len(exp_vals) == 0 else "Inconsistent")

        rows.append({
            "name": sid,
            "SportFreq": sport,
            "Experience": exp,
        })

    out = pd.DataFrame(rows).sort_values("name").reset_index(drop=True)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(out_csv, index=False, encoding="utf-8-sig")
    return out


def main():
    ap = argparse.ArgumentParser(description="Build group_manifest.csv from long_format.csv")
    ap.add_argument("--long-csv", type=Path, required=True)
    ap.add_argument("--out", type=Path, default=Path("group_manifest.csv"))
    args = ap.parse_args()

    out = build_manifest(args.long_csv, args.out)
    print(json.dumps({"rows": int(len(out)), "out": str(args.out)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
