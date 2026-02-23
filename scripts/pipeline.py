#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import argparse
import subprocess
import sys


def run(cmd: list[str]):
    print("$", " ".join(cmd))
    p = subprocess.run(cmd)
    if p.returncode != 0:
        raise SystemExit(p.returncode)


def main():
    ap = argparse.ArgumentParser(description="One-click pipeline: wide Excel -> long -> model -> research analysis")
    ap.add_argument("--excel", required=True, type=Path)
    ap.add_argument("--sheet", default="0")
    ap.add_argument("--out-root", default=Path("results"), type=Path)
    ap.add_argument("--python", default=sys.executable)
    ap.add_argument("--skip-model", action="store_true", help="Skip scripts/run_analysis.py")
    ap.add_argument("--skip-research", action="store_true", help="Skip research modules")
    ap.add_argument("--skip-diagnostics", action="store_true", help="Skip scripts/diagnostics_lmm.py")
    ap.add_argument("--skip-bundle", action="store_true", help="Skip scripts/build_report_md.py")

    # Optional R re-run (paper-ready inference)
    ap.add_argument("--with-r", action="store_true", help="If Rscript is available, run scripts/run_analysis_R.R and write results under <out-root>/r_model")
    ap.add_argument("--rscript", default="Rscript", help="Rscript executable name/path (default: Rscript)")
    ap.add_argument("--r-df-method", default="Satterthwaite", help="Satterthwaite|Kenward-Roger")
    ap.add_argument("--r-p-adjust", default="Holm", help="Holm|bonferroni|fdr|none")
    ap.add_argument(
        "--with-r-robustness",
        action="store_true",
        help="If Rscript is available, run R re-fit twice (Satterthwaite + Kenward-Roger) and write a p-value comparison table",
    )

    args = ap.parse_args()

    out_long = args.out_root / "long"
    out_model = args.out_root / "model"
    out_research = args.out_root / "research"
    out_diag = args.out_root / "diagnostics"

    run([
        args.python, "scripts/transform_wide_to_long.py",
        "--excel", str(args.excel),
        "--sheet", str(args.sheet),
        "--out-dir", str(out_long),
    ])

    # auto-build participant-level group manifest (no manual filling)
    run([
        args.python, "scripts/build_group_manifest.py",
        "--long-csv", str(out_long / "long_format.csv"),
        "--out", str(args.out_root / "group_manifest.csv"),
    ])

    if not args.skip_model:
        # keep existing core model workflow
        run([
            args.python, "scripts/run_analysis.py",
            "--long-csv", str(out_long / "long_format.csv"),
            "--out-dir", str(out_model),
        ])

    if not args.skip_research:
        # research workflow (modular)
        run([
            args.python, "scripts/analysis_s_items.py",
            "--long-csv", str(out_long / "long_format.csv"),
            "--out-dir", str(out_research),
        ])
        run([
            args.python, "scripts/analysis_b_items.py",
            "--long-csv", str(out_long / "long_format.csv"),
            "--out-dir", str(out_research),
        ])
        run([
            args.python, "scripts/report_summary.py",
            "--long-csv", str(out_long / "long_format.csv"),
            "--research-dir", str(out_research),
            "--out", str(out_research / "analysis_narrative.md"),
        ])

    if not args.skip_diagnostics:
        # diagnostics workflow for model-source and robustness checks
        run([
            args.python, "scripts/diagnostics_lmm.py",
            "--long-csv", str(out_long / "long_format.csv"),
            "--out-dir", str(out_diag),
        ])

        # One-page, journal-style residual diagnostics for the primary model
        run([
            args.python, "scripts/report_model_diagnostics.py",
            "--long-csv", str(out_long / "long_format.csv"),
            "--out-dir", str(out_diag),
        ])

    # write provenance for reproducibility (packages, git commit, argv)
    run([
        args.python, "scripts/write_provenance.py",
        "--results-root", str(args.out_root),
        "--excel", str(args.excel),
        "--sheet", str(args.sheet),
    ])

    # Optional: re-run main model in R for paper-ready inference
    if args.with_r or args.with_r_robustness:
        rscript_path = None
        try:
            rscript_path = subprocess.check_output(["bash", "-lc", f"command -v {args.rscript}"], text=True).strip()
        except Exception:
            rscript_path = ""

        if not rscript_path:
            print("[pipeline] Rscript not found; skipping R re-run.")
        else:
            def _run_r(out_dir: Path, df_method: str):
                cmd = [
                    args.rscript,
                    "scripts/run_analysis_R.R",
                    "--long-csv", str(out_long / "long_format.csv"),
                    "--out-dir", str(out_dir),
                    "--df-method", str(df_method),
                    "--p-adjust", str(args.r_p_adjust),
                    # KR requires REML=TRUE; for robustness we keep both runs on REML for comparability.
                    "--reml", "TRUE" if ("Kenward" in str(df_method) or args.with_r_robustness) else "auto",
                ]
                print("$", " ".join(cmd))
                p = subprocess.run(cmd)
                if p.returncode != 0:
                    print(f"[pipeline] R re-run failed for df-method={df_method} (returncode={p.returncode}).")
                return p.returncode

            if args.with_r_robustness:
                # Primary: Satterthwaite; Robustness: Kenward-Roger
                rc1 = _run_r(args.out_root / "r_model", "Satterthwaite")
                rc2 = _run_r(args.out_root / "r_model_KR", "Kenward-Roger")

                # If both exist, write a simple p-value comparison table (fixed effects)
                try:
                    import pandas as pd

                    p_sat = args.out_root / "r_model" / "fixed_effects_afford4.csv"
                    p_kr = args.out_root / "r_model_KR" / "fixed_effects_afford4.csv"
                    if p_sat.exists() and p_kr.exists():
                        a = pd.read_csv(p_sat)
                        b = pd.read_csv(p_kr)
                        key = "term" if "term" in a.columns and "term" in b.columns else ("Term" if "Term" in a.columns and "Term" in b.columns else None)
                        if key:
                            aa = a[[c for c in a.columns if c in {key, "estimate", "std.error", "df", "statistic", "p.value", "conf.low", "conf.high"}]].copy()
                            bb = b[[c for c in b.columns if c in {key, "estimate", "std.error", "df", "statistic", "p.value", "conf.low", "conf.high"}]].copy()
                            aa = aa.rename(columns={"p.value": "p_sat", "df": "df_sat", "statistic": "t_sat"})
                            bb = bb.rename(columns={"p.value": "p_kr", "df": "df_kr", "statistic": "t_kr"})
                            m = aa.merge(bb[[key, "p_kr", "df_kr", "t_kr"]], on=key, how="outer")
                            if "p_sat" in m.columns and "p_kr" in m.columns:
                                m["p_delta_abs"] = (m["p_kr"] - m["p_sat"]).abs()
                            m.to_csv(args.out_root / "r_model_pvalue_compare_fixed_effects_afford4.csv", index=False, encoding="utf-8-sig")
                except Exception as e:
                    print(f"[pipeline] Failed to write R p-value comparison table: {e}")

                if rc1 != 0 or rc2 != 0:
                    print("[pipeline] R robustness run had failures; continuing without blocking Python outputs.")

            elif args.with_r:
                _run_r(args.out_root / "r_model", str(args.r_df_method))

    if not args.skip_bundle:
        # build one markdown bundle for easy sharing/review
        run([
            args.python, "scripts/build_report_md.py",
            "--results-root", str(args.out_root),
            "--out", str(args.out_root / "analysis_report_bundle.md"),
        ])

        # build a detailed key-results bundle (more focused + richer detail)
        run([
            args.python, "scripts/build_report_key_md.py",
            "--results-root", str(args.out_root),
            "--out", str(args.out_root / "analysis_report_key.md"),
            "--max-rows", "5000",
        ])

        # build data-first report (tables embedded directly, minimal index dependency)
        run([
            args.python, "scripts/build_report_data_md.py",
            "--results-root", str(args.out_root),
            "--out", str(args.out_root / "analysis_report_data.md"),
            "--max-rows", "5000",
        ])

    print("\nDone. Outputs:")
    print("-", out_long)
    print("-", out_model)
    print("-", out_research)
    print("-", out_diag)


if __name__ == "__main__":
    main()
