#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

REPO = Path(__file__).resolve().parents[1]


def run(cmd: list[str], cwd: Path | None = None) -> None:
    print('$', ' '.join(cmd))
    p = subprocess.run(cmd, cwd=cwd or REPO)
    if p.returncode != 0:
        raise SystemExit(p.returncode)


def capture(cmd: list[str], cwd: Path | None = None) -> str:
    print('$', ' '.join(cmd))
    p = subprocess.run(cmd, cwd=cwd or REPO, capture_output=True, text=True)
    if p.returncode != 0:
        raise SystemExit(p.returncode)
    return p.stdout



def main() -> int:
    print('== clean main smoke checks ==')

    run([sys.executable, 'scripts/check_doc_consistency.py'])
    print('[OK] doc consistency')

    run([sys.executable, 'scripts/check_main_entrypoints.py'])
    print('[OK] main entrypoints')

    cli_checks = [
        (
            [sys.executable, 'scripts/pipeline.py', '--help'],
            ['--excel', '--sheet', '--out-root', '--skip-descriptive', '--skip-significance', '--with-qc'],
            [['Clean pipeline'], ['descriptive', 'significance'], ['overall', 'experience']],
        ),
        (
            [sys.executable, 'scripts/descriptive_pipeline.py', '--help'],
            ['--long-csv', '--out-dir', '--with-qc'],
            [['Descriptive-only pipeline'], ['overall', 'experience']],
        ),
        (
            [sys.executable, 'scripts/significance_pipeline.py', '--help'],
            ['--long-csv', '--out-dir', '--python', '--with-qc'],
            [['Significance-only pipeline'], ['overall', 'experience']],
        ),
        (
            [sys.executable, 'scripts/run_item_level_lmm.py', '--help'],
            ['--long-csv', '--out-dir', '--exclude-subjects', '--p-adjust', '--df-method', '--rscript'],
            [['item-level'], ['LMM'], ['fixed effects', 'consistent across', 'DVs']],
        ),
    ]
    for cmd, required_flags, required_phrase_groups in cli_checks:
        out = capture(cmd)
        for flag in required_flags:
            if flag not in out:
                raise SystemExit(f'Missing expected CLI flag in help output: {flag}')
        for group in required_phrase_groups:
            for token in group:
                if token not in out:
                    raise SystemExit(f'Missing expected CLI help token: {token}')
    print('[OK] CLI help sanity')

    tmpdir = Path(tempfile.mkdtemp(prefix='spss_smoke_'))
    try:
        out_root = tmpdir / 'results'
        run([sys.executable, str(REPO / 'scripts' / 'build_results_guide.py'), '--out-root', str(out_root)], cwd=REPO)

        md = out_root / 'RESULTS_GUIDE.md'
        png = out_root / 'RESULTS_GUIDE.png'
        if not md.exists():
            raise SystemExit('Missing RESULTS_GUIDE.md from build_results_guide.py smoke run')
        if not png.exists():
            raise SystemExit('Missing RESULTS_GUIDE.png from build_results_guide.py smoke run')

        text = md.read_text(encoding='utf-8')
        required_snippets = [
            'First reading order',
            'descriptive/qc/overall/png/',
            'significance/qc/overall/core_model/',
            'significance/qc/experience/wwr_polynomial_group_round/',
            'Prefer `qc` over `raw` for formal interpretation.',
            'Read `png/` first for pattern, then `csv/` for exact numbers.',
        ]
        for snippet in required_snippets:
            if snippet not in text:
                raise SystemExit(f'Missing expected text in RESULTS_GUIDE.md: {snippet}')

        print('[OK] build_results_guide output generation')
        print(f'[OK] temp output: {out_root}')
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

    print('ALL SMOKE CHECKS PASSED')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
