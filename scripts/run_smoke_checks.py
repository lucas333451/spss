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



def main() -> int:
    print('== clean main smoke checks ==')

    run([sys.executable, 'scripts/check_doc_consistency.py'])
    print('[OK] doc consistency')

    run([sys.executable, 'scripts/check_main_entrypoints.py'])
    print('[OK] main entrypoints')

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
