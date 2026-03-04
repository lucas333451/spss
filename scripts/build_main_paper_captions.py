#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import argparse
import json
import pandas as pd


def _safe_read_csv(p: Path):
    try:
        if p.exists():
            return pd.read_csv(p)
    except Exception:
        return None
    return None


def _stat_hint(fig_name: str, results_root: Path) -> str:
    n = fig_name.lower()
    # lightweight hints from key result tables
    if "task2_s_model_aic" in n:
        f = results_root / "research/analysis-2/task2/experience/qc/analysis2_core_imm_suite_s_models.csv"
        df = _safe_read_csv(f)
        if df is not None and not df.empty and "AIC" in df.columns:
            ok = df[df.get("Status", "ok") == "ok"] if "Status" in df.columns else df
            if not ok.empty:
                return f"AIC range across shown models: {ok['AIC'].min():.2f} to {ok['AIC'].max():.2f}."
    if "task2_b_model_aic" in n:
        f = results_root / "research/analysis-2/task2/experience/qc/analysis2_core_imm_suite_b_models.csv"
        df = _safe_read_csv(f)
        if df is not None and not df.empty and "AIC" in df.columns:
            ok = df[df.get("Status", "ok") == "ok"] if "Status" in df.columns else df
            if not ok.empty:
                return f"AIC range across shown models: {ok['AIC'].min():.2f} to {ok['AIC'].max():.2f}."
    if "task1_scene" in n:
        f = results_root / "research/analysis-2/task1/experience/qc/analysis2_scene_stage_gap_long.csv"
        df = _safe_read_csv(f)
        if df is not None and not df.empty and "p_holm" in df.columns:
            sig = int((pd.to_numeric(df["p_holm"], errors="coerce") < 0.05).fillna(False).sum())
            return f"Significant cells after Holm correction: {sig}."
    return ""


def _caption_cn(label: str, purpose: str, hint: str) -> str:
    base = f"{label}：{purpose}"
    if hint:
        base += f" 统计提示：{hint}"
    return base


def _caption_en(label: str, purpose: str, hint: str) -> str:
    base = f"{label}. {purpose}"
    if hint:
        base += f" Statistical note: {hint}"
    return base


def main():
    ap = argparse.ArgumentParser(description="Generate bilingual manuscript-ready captions for main paper figures")
    ap.add_argument("--results-root", type=Path, default=Path("results"))
    ap.add_argument("--fig-dir", type=Path, default=Path("results/figures_main_paper"))
    args = ap.parse_args()

    manifest = args.fig_dir / "figures_main_manifest.json"
    if not manifest.exists():
        raise SystemExit(f"Missing manifest: {manifest}. Run build_main_paper_figures.py first.")

    data = json.loads(manifest.read_text(encoding="utf-8"))
    rows = data.get("selected", [])

    lines = [
        "# Main Paper Figure Captions (Bilingual)",
        "",
        "## 中文",
        "",
    ]

    en_lines = ["## English", ""]

    for r in rows:
        label = r.get("label", "Figure")
        purpose = r.get("purpose", "")
        file = r.get("file", "")
        hint = _stat_hint(file, args.results_root)

        lines.append(f"- **{label}** (`{file}`): {_caption_cn(label, purpose, hint)}")
        en_lines.append(f"- **{label}** (`{file}`): {_caption_en(label, purpose, hint)}")

    out = args.fig_dir / "FIGURES_MAIN_CAPTIONS.md"
    out.write_text("\n".join(lines + [""] + en_lines), encoding="utf-8")
    print(json.dumps({"out": str(out), "n": len(rows)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
