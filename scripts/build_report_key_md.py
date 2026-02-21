#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import argparse
import json
import glob
import pandas as pd

KEY_FILES = [
    # overall narrative
    "research/analysis_narrative.md",

    # model layer
    "model/model_comparison.csv",
    "model/table_fixed_effects.csv",
    "model/table_main_interactions.csv",
    "model/table_simple_effects_complexity_by_wwr.csv",

    # S-item (main)
    "research/table_angle1_main_interactions_all_dv.csv",
    "research/table_angle2_round_interactions_all_dv.csv",
    "research/group_comparisons_item_level.csv",
    "research/group_complexity_mean_table.csv",
    "research/group_complexity_delta_significance.csv",
    "research/group_complexity_mean_table_by_wwr.csv",
    "research/group_complexity_delta_significance_by_wwr.csv",
    "research/group_complexity_delta_by_round.csv",
    "research/group_complexity_delta_round_shift.csv",
    "research/round_icc_by_group.csv",

    # group2 outputs
    "research/group2_comparisons_item_level.csv",
    "research/group2_complexity_mean_table.csv",
    "research/group2_complexity_delta_significance.csv",
    "research/group2_comparisons_item_level_sportfreqgroup.csv",
    "research/group2_comparisons_item_level_experiencegroup.csv",

    # B-item
    "research/b_items_condition_means.csv",
    "research/b_items_group_comparisons.csv",

    # diagnostics
    "diagnostics/analysis_report.md",
    "diagnostics/model_comparison_interactions.csv",
    "diagnostics/lrt_comparison.csv",
    "diagnostics/main_effect_stability_by_random_structure.csv",
]

KEY_GLOBS = [
    "research/figures/group_complexity_delta_S*.png",
    "research/figures/group_complexity_heatmap_S*.png",
    "research/figures/interaction_S*_by_sportfreqgroup.png",
    "research/figures/round_diff_S*_by_sportfreqgroup.png",
    "diagnostics/figures/*.png",
]


def _read_text(path: Path, max_chars: int = 300000) -> str:
    try:
        s = path.read_text(encoding="utf-8", errors="ignore")
    except Exception as e:
        return f"<read failed: {e}>"
    if len(s) > max_chars:
        return s[:max_chars] + "\n\n... (truncated)"
    return s


def _csv_to_markdown(path: Path, max_rows: int = 5000) -> str:
    try:
        df = pd.read_csv(path)
    except Exception as e:
        return f"`Failed to read CSV: {e}`"

    n = len(df)
    if n == 0:
        return "(empty table)"
    if n > max_rows:
        return (
            f"Rows: {n} (showing first {max_rows})\n\n"
            + df.head(max_rows).to_markdown(index=False)
            + "\n\n... (truncated)"
        )
    return f"Rows: {n}\n\n" + df.to_markdown(index=False)


def _resolve_key_paths(results_root: Path) -> tuple[list[Path], list[str]]:
    found: list[Path] = []
    missing: list[str] = []

    for rel in KEY_FILES:
        p = results_root / rel
        if p.exists() and p.is_file():
            found.append(p)
        else:
            missing.append(rel)

    for pat in KEY_GLOBS:
        matches = sorted(Path(x) for x in glob.glob(str(results_root / pat)))
        found.extend([m for m in matches if m.is_file()])

    # de-dup preserve order
    dedup: list[Path] = []
    seen = set()
    for p in found:
        key = str(p.resolve())
        if key not in seen:
            seen.add(key)
            dedup.append(p)
    return dedup, missing


def _load_provenance(results_root: Path) -> dict | None:
    p = results_root / "provenance.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def build_key_report(results_root: Path, out_file: Path, max_rows: int) -> None:
    files, missing = _resolve_key_paths(results_root)
    prov = _load_provenance(results_root)

    lines: list[str] = []
    lines.append("# Analysis Key Report (for direct interpretation)")
    lines.append("")
    lines.append("This report only bundles key outputs needed for interpretation and discussion.")
    lines.append(f"Results root: `{results_root}`")
    lines.append(f"Included files: {len(files)}")

    if prov:
        lines.append("")
        lines.append("## Provenance (reproducibility fingerprint)")
        ts = prov.get("timestamp_utc")
        git_commit = (prov.get("git") or {}).get("commit")
        is_clean = (prov.get("git") or {}).get("is_clean")
        pyv = (prov.get("python") or {}).get("version")
        inputs = prov.get("inputs") or {}
        rver = (prov.get("r") or {}).get("version")
        pkgs = prov.get("python_packages") or {}

        lines.append(f"- timestamp_utc: `{ts}`")
        lines.append(f"- git_commit: `{git_commit}`")
        lines.append(f"- git_clean: `{is_clean}`")
        lines.append(f"- excel: `{inputs.get('excel')}`")
        lines.append(f"- sheet: `{inputs.get('sheet')}`")
        if pyv:
            lines.append(f"- python: `{str(pyv).splitlines()[0]}`")
        if rver:
            lines.append(f"- R: `{str(rver).splitlines()[0]}`")

        # Compact package list for easy reviewer/auditor checks
        want = ["pandas","numpy","openpyxl","statsmodels","scipy","seaborn","matplotlib","pingouin"]
        pairs = []
        for w in want:
            v = pkgs.get(w)
            if v:
                pairs.append(f"{w}=={v}")
        if pairs:
            lines.append("")
            lines.append("**Python packages (key):**")
            lines.append("- " + ", ".join(pairs))

    lines.append("")

    if missing:
        lines.append("## Missing expected files (may depend on run options)")
        for m in missing:
            lines.append(f"- `{m}`")
        lines.append("")

    lines.append("## Included file index")
    for p in files:
        lines.append(f"- `{p.relative_to(results_root)}`")
    lines.append("")
    lines.append("---")
    lines.append("")

    for p in files:
        rel = p.relative_to(results_root)
        suf = p.suffix.lower()
        lines.append(f"## {rel}")
        lines.append("")

        if suf == ".csv":
            lines.append(_csv_to_markdown(p, max_rows=max_rows))
        elif suf in {".md", ".txt", ".log"}:
            txt = _read_text(p)
            if suf == ".md":
                lines.append(txt)
            else:
                lines.append("```text")
                lines.append(txt)
                lines.append("```")
        elif suf in {".png", ".jpg", ".jpeg", ".webp", ".gif"}:
            lines.append(f"Image file: `{rel}`")
        else:
            lines.append(f"(unsupported preview) `{rel}`")

        lines.append("")
        lines.append("---")
        lines.append("")

    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text("\n".join(lines), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser(description="Build a detailed key-results markdown bundle")
    ap.add_argument("--results-root", type=Path, default=Path("results"))
    ap.add_argument("--out", type=Path, default=Path("results/analysis_report_key.md"))
    ap.add_argument("--max-rows", type=int, default=5000)
    args = ap.parse_args()

    build_key_report(args.results_root, args.out, max_rows=args.max_rows)
    print(json.dumps({
        "results_root": str(args.results_root),
        "out": str(args.out),
        "max_rows": args.max_rows,
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
