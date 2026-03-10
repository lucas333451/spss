#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys

REPO = Path(__file__).resolve().parents[1]

# Only scan user-facing docs / notebooks that should stay aligned with clean main.
TARGETS = [
    REPO / 'README.md',
    REPO / 'README_zh.md',
    REPO / 'RESULTS_MAP.md',
    REPO / 'docs' / 'COLAB_GUIDE.md',
    REPO / 'docs' / 'PROJECT_OVERVIEW.md',
    REPO / 'docs' / 'RESULTS_READING_GUIDE.md',
    REPO / 'docs' / 'RESULTS_READING_GUIDE.zh.md',
    REPO / 'notebooks' / 'colab_setup.ipynb',
    REPO / 'notebooks' / 'spss_colab.ipynb',
]

FORBIDDEN = [
    'results/model',
    'results/research',
    'long/model/research',
]

ALLOWED_CONTEXT_SNIPPETS = [
    'raw 分支',
    'raw branch',
    '旧版',
    'legacy',
    'historical',
    '不要把旧版',
    '如果你明确要',
    '那不是当前 `main` 的默认主阅读面',
    '才回到旧版逻辑',
    '旧的 `results/',
    'not the default reading surface',
    'go back to legacy outputs',
    'old `results/',
]


def is_allowed_context(line: str) -> bool:
    s = line.lower()
    return any(tok.lower() in s for tok in ALLOWED_CONTEXT_SNIPPETS)



def main() -> int:
    failures: list[str] = []

    for path in TARGETS:
        if not path.exists():
            continue
        text = path.read_text(encoding='utf-8')
        for i, line in enumerate(text.splitlines(), start=1):
            for bad in FORBIDDEN:
                if bad in line:
                    if is_allowed_context(line):
                        continue
                    failures.append(f'{path.relative_to(REPO)}:{i}: forbidden clean-main drift -> {bad}')

    if failures:
        print('DOC CONSISTENCY CHECK FAILED')
        for x in failures:
            print(x)
        return 1

    print('DOC CONSISTENCY CHECK PASSED')
    for path in TARGETS:
        if path.exists():
            print(path.relative_to(REPO))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
