#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import argparse
import json
import pandas as pd

TEXT_SUFFIXES = {".md", ".txt", ".log"}
JSON_SUFFIXES = {".json"}
CSV_SUFFIXES = {".csv"}
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif"}


def _read_text(path: Path, max_chars: int = 20000) -> str:
    try:
        s = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return "<read failed>"
    if len(s) > max_chars:
        return s[:max_chars] + "\n\n... (truncated)"
    return s


def _csv_to_markdown(path: Path, max_rows: int = 500) -> str:
    try:
        df = pd.read_csv(path)
    except Exception as e:
        return f"`Failed to read CSV: {e}`"

    n = len(df)
    if n == 0:
        return "(empty table)"

    if n > max_rows:
        head = df.head(max_rows)
        return (
            f"Rows: {n} (showing first {max_rows})\n\n"
            + head.to_markdown(index=False)
            + "\n\n... (truncated)"
        )
    return f"Rows: {n}\n\n" + df.to_markdown(index=False)


def build_report(results_root: Path, out_file: Path, max_rows: int) -> None:
    all_files = sorted([p for p in results_root.rglob("*") if p.is_file()])

    lines: list[str] = []
    lines.append("# Analysis Report Bundle (for sharing)")
    lines.append("")
    lines.append(f"Results root: `{results_root}`")
    lines.append(f"Total files: {len(all_files)}")
    lines.append("")

    lines.append("## File Index")
    for f in all_files:
        lines.append(f"- `{f.relative_to(results_root)}`")
    lines.append("")

    lines.append("---")
    lines.append("")

    for f in all_files:
        rel = f.relative_to(results_root)
        suf = f.suffix.lower()
        lines.append(f"## {rel}")

        if suf in CSV_SUFFIXES:
            lines.append("")
            lines.append(_csv_to_markdown(f, max_rows=max_rows))
            lines.append("")

        elif suf in JSON_SUFFIXES:
            lines.append("")
            try:
                obj = json.loads(_read_text(f, max_chars=500000))
                pretty = json.dumps(obj, ensure_ascii=False, indent=2)
            except Exception:
                pretty = _read_text(f)
            lines.append("```json")
            lines.append(pretty)
            lines.append("```")
            lines.append("")

        elif suf in TEXT_SUFFIXES:
            lines.append("")
            txt = _read_text(f)
            if suf == ".md":
                lines.append(txt)
            else:
                lines.append("```text")
                lines.append(txt)
                lines.append("```")
            lines.append("")

        elif suf in IMAGE_SUFFIXES:
            lines.append("")
            lines.append(f"Image file: `{rel}`")
            lines.append("")

        else:
            lines.append("")
            lines.append(f"(binary/unsupported preview) `{rel}`")
            lines.append("")

        lines.append("---")
        lines.append("")

    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text("\n".join(lines), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser(description="Build one markdown bundle from results/ for easy sharing")
    ap.add_argument("--results-root", type=Path, default=Path("results"))
    ap.add_argument("--out", type=Path, default=Path("results/analysis_report_bundle.md"))
    ap.add_argument("--max-rows", type=int, default=500, help="Max rows shown per CSV table")
    args = ap.parse_args()

    build_report(args.results_root, args.out, max_rows=args.max_rows)
    print(json.dumps({
        "results_root": str(args.results_root),
        "out": str(args.out),
        "max_rows": args.max_rows
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
