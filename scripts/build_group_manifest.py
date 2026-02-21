#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import argparse
import json
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


def build_manifest(long_csv: Path, out_csv: Path) -> pd.DataFrame:
    """Build participant manifest with group labels + scene presentation order.

    Output columns start with: name,SportFreq,Experience,Order
    Then 12 trials (Block1 Pos1..6, then Block2 Pos1..6):
    - trialXX_scene  (e.g., WWR45_C1)
    - trialXX_WWR    (15/45/75)
    - trialXX_Cond   (C0/C1)
    - trialXX_Complexity (0/1)

    This is designed to support downstream eye-tracking/EEG alignment.
    """

    df = pd.read_csv(long_csv)

    required = ["SubjectID", "SportFreqGroup", "ExperienceGroup", "Order"]
    miss = [c for c in required if c not in df.columns]
    if miss:
        raise SystemExit(f"Missing required columns in long CSV: {miss}")

    x = df[["SubjectID", "SportFreqGroup", "ExperienceGroup", "Order"]].dropna(subset=["SubjectID"]).copy()
    x["SubjectID"] = x["SubjectID"].astype(str).str.strip()
    x = x[x["SubjectID"] != ""]

    rows = []
    for sid, g in x.groupby("SubjectID", dropna=False):
        sport_vals = sorted({str(v) for v in g["SportFreqGroup"].dropna().astype(str)})
        exp_vals = sorted({str(v) for v in g["ExperienceGroup"].dropna().astype(str)})
        order_vals = sorted({int(v) for v in pd.to_numeric(g["Order"], errors="coerce").dropna().astype(int).tolist()})

        sport = sport_vals[0] if len(sport_vals) == 1 else ("Unknown" if len(sport_vals) == 0 else "Inconsistent")
        exp = exp_vals[0] if len(exp_vals) == 1 else ("Unknown" if len(exp_vals) == 0 else "Inconsistent")
        order = order_vals[0] if len(order_vals) == 1 else (None if len(order_vals) == 0 else -1)

        row = {
            "name": sid,
            "SportFreq": sport,
            "Experience": exp,
            "Order": order if order is not None else "Unknown",
        }

        # Fill 12-trial scene sequence for known order
        if isinstance(order, int) and order in MAPPING:
            for t in range(1, 13):
                block = 1 if t <= 6 else 2
                pos = t if t <= 6 else (t - 6)
                wwr, cond = MAPPING[order][block][pos]
                scene = f"WWR{int(wwr)}_{cond}"
                complexity = 1 if cond == "C1" else 0

                tag = f"trial{t:02d}"
                row[f"{tag}_scene"] = scene
                row[f"{tag}_WWR"] = int(wwr)
                row[f"{tag}_Cond"] = cond
                row[f"{tag}_Complexity"] = complexity
        else:
            for t in range(1, 13):
                tag = f"trial{t:02d}"
                row[f"{tag}_scene"] = "Unknown"
                row[f"{tag}_WWR"] = "Unknown"
                row[f"{tag}_Cond"] = "Unknown"
                row[f"{tag}_Complexity"] = "Unknown"

        rows.append(row)

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
