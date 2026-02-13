#!/usr/bin/env python3
from pathlib import Path
import argparse
import pandas as pd


def inspect(path: Path, out_dir: Path):
    xls = pd.ExcelFile(path)
    out_dir.mkdir(parents=True, exist_ok=True)

    summary_lines = [f"# Excel inspection: {path}", ""]
    for sheet in xls.sheet_names:
        df = pd.read_excel(path, sheet_name=sheet)
        summary_lines.append(f"## Sheet: {sheet}")
        summary_lines.append(f"- shape: {df.shape[0]} rows x {df.shape[1]} cols")
        summary_lines.append("- columns:")
        for c in df.columns:
            summary_lines.append(f"  - {c}")
        summary_lines.append("")

        cols_df = pd.DataFrame({"column": df.columns, "dtype": [str(t) for t in df.dtypes]})
        safe_sheet = sheet.replace('/', '_')
        cols_df.to_csv(out_dir / f"columns_{safe_sheet}.csv", index=False, encoding="utf-8-sig")

    (out_dir / "inspection.md").write_text("\n".join(summary_lines), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser(description="Inspect questionnaire Excel and export sheet/column summary")
    ap.add_argument("excel", type=Path)
    ap.add_argument("--out", type=Path, default=Path("results/inspection"))
    args = ap.parse_args()

    inspect(args.excel, args.out)
    print(f"Done. See: {args.out}")


if __name__ == "__main__":
    main()
