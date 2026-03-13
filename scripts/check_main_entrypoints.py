#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import re
import subprocess
import sys

REPO = Path(__file__).resolve().parents[1]

REQUIRED_FILES = [
    REPO / 'README.md',
    REPO / 'README_zh.md',
    REPO / 'RESULTS_MAP.md',
    REPO / 'docs' / 'COLAB_GUIDE.md',
    REPO / 'docs' / 'PROJECT_OVERVIEW.md',
    REPO / 'docs' / 'RESULTS_READING_GUIDE.md',
    REPO / 'docs' / 'RESULTS_READING_GUIDE.zh.md',
    REPO / 'docs' / 'R_SETUP_FOR_ITEM_LEVEL_LMM.md',
    REPO / 'notebooks' / 'colab_setup.ipynb',
    REPO / 'notebooks' / 'spss_colab.ipynb',
    REPO / 'scripts' / 'check_doc_consistency.py',
    REPO / 'scripts' / 'build_results_guide.py',
    REPO / 'scripts' / 'check_r_item_level_lmm.py',
    REPO / 'scripts' / 'run_item_level_lmm.py',
    REPO / 'scripts' / 'pipeline.py',
    REPO / 'scripts' / 'descriptive_pipeline.py',
    REPO / 'scripts' / 'significance_pipeline.py',
]

README_LINK_SOURCES = [
    REPO / 'README.md',
    REPO / 'README_zh.md',
]

LINK_RE = re.compile(r'\((\./[^)]+)\)')


def check_required_files() -> list[str]:
    failures: list[str] = []
    for path in REQUIRED_FILES:
        if not path.exists():
            failures.append(f'missing required file: {path.relative_to(REPO)}')
    return failures



def check_readme_links() -> list[str]:
    failures: list[str] = []
    for src in README_LINK_SOURCES:
        text = src.read_text(encoding='utf-8')
        for rel in LINK_RE.findall(text):
            target = (src.parent / rel).resolve()
            if not target.exists():
                failures.append(f'broken README link: {src.relative_to(REPO)} -> {rel}')
    return failures



def run_doc_consistency() -> list[str]:
    cmd = [sys.executable, str(REPO / 'scripts' / 'check_doc_consistency.py')]
    p = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True)
    if p.returncode != 0:
        msg = p.stdout.strip() or p.stderr.strip() or 'unknown failure'
        return [f'doc consistency check failed: {msg}']
    return []



def main() -> int:
    failures: list[str] = []
    failures.extend(check_required_files())
    failures.extend(check_readme_links())
    failures.extend(run_doc_consistency())

    if failures:
        print('MAIN ENTRYPOINT CHECK FAILED')
        for x in failures:
            print(x)
        return 1

    print('MAIN ENTRYPOINT CHECK PASSED')
    print('Required files present:', len(REQUIRED_FILES))
    print('README link sources checked:', len(README_LINK_SOURCES))
    print('Doc consistency script: passed')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
