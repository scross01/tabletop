# Plan 001: Add ruff (linter, formatter, import sorter)

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md` — unless a reviewer dispatched you and told you they
> maintain the index.
>
> **Drift check (run first)**: `git diff --stat ecfde61..HEAD -- pyproject.toml tabletop/ tests/`
> If any in-scope file changed since this plan was written, compare the
> "Current state" excerpts against the live code before proceeding; on a
> mismatch, treat it as a STOP condition.

## Status

- **Priority**: P1
- **Effort**: S
- **Risk**: LOW
- **Depends on**: none
- **Category**: dx
- **Planned at**: commit `ecfde61`, 2026-06-18

## Why this matters

The repo has no linter, formatter, or import sorter. Every commit can introduce
inconsistent style, unused imports, or subtle bugs (e.g. bare `except:`, mutable
defaults). Adding ruff as a one-stop tool solves all three — lint, format, and
sort imports — with a single dependency and near-zero config. This establishes
the code quality baseline that plan 002 (CI) will enforce.

## Current state

- `pyproject.toml` has no `[tool.ruff]` section and no ruff dev dependency.
- Existing code style is inconsistent: some files use 100+ character lines
  (`parser.py:366`), import ordering varies, and there are a few minor issues
  ruff would flag (e.g. `cli.py:27` unused fallback import on 3.12+).
- The repo uses `from __future__ import annotations` everywhere, single-quoted
  strings, and 4-space indentation.

Exemplar of current style (any file — they are all consistent on basics):
```python
"""Table transforms: sort, filter, column selection/removal."""

from __future__ import annotations

import re
from typing import Any

from .parser import Table
```

## Commands you will need

| Purpose               | Command                       | Expected on success |
|-----------------------|-------------------------------|---------------------|
| Install ruff          | `uv add --dev ruff`           | exit 0              |
| Run ruff check        | `uv run ruff check`           | exit 0, no output   |
| Run ruff format       | `uv run ruff format --check`  | exit 0, no output   |
| Run tests             | `uv run pytest`               | all pass            |

## Scope

**In scope** (the only files you should modify):
- `pyproject.toml` — add ruff dev dependency and `[tool.ruff]` section
- `tabletop/cli.py` — ruff may fix minor issues
- `tabletop/parser.py` — ruff may fix minor issues
- `tabletop/output.py` — ruff may fix minor issues
- `tabletop/transforms.py` — ruff may fix minor issues
- `tests/test_cli.py` — ruff may fix minor issues
- `tests/test_parser.py` — ruff may fix minor issues
- `tests/test_transforms.py` — ruff may fix minor issues
- `tests/test_output.py` — ruff may fix minor issues
- `tests/test_fixtures.py` — ruff may fix minor issues
- `tests/conftest.py` — ruff may fix minor issues

**Out of scope** (do NOT touch):
- `tabletop/__init__.py` — empty file, leave it
- `tabletop/__main__.py` — 4 lines, no changes needed
- Any `.md` file, `demo.tape`, `Makefile`, `.gitignore` — not Python

## Git workflow

- Branch: `advisor/001-add-ruff-linter`
- Commit style: conventional commits (`git log --oneline` uses `feat:`, `fix:`, `chore:` prefixes)
- Three commits: (1) add ruff dep + config, (2) run `ruff check --fix`, (3) run `ruff format`
- Do NOT push or open a PR unless instructed

## Steps

### Step 1: Add ruff dev dependency and config

1. Run `uv add --dev ruff` to add ruff to `[dependency-groups.dev]` in `pyproject.toml`.
2. Add the following `[tool.ruff]` section to `pyproject.toml` (after any existing tool sections):

```toml
[tool.ruff]
target-version = "py312"
line-length = 100

[tool.ruff.lint]
select = [
    "E",   # pycodestyle errors
    "F",   # pyflakes (catches unused imports, undefined names)
    "I",   # isort (import ordering)
    "N",   # naming conventions
    "W",   # pycodestyle warnings
    "UP",  # pyupgrade (modernize for target version)
]
ignore = [
    "E501",  # line-too-long — handled by formatter
]

[tool.ruff.lint.per-file-ignores]
"tests/*" = ["N802", "N803", "N806"]  # allow test function names like test_parse_basic
```

3. Verify the config is valid:

**Verify**: `uv run ruff check` → exits 0 with no output (no violations expected yet, ruff is not yet enforcing on existing code — the `--fix` step will handle violations)

**Verify**: `uv run ruff format --check` → exits 0, may list files that would be reformatted (that's expected)

### Step 2: Run ruff check with auto-fix

```bash
uv run ruff check --fix
```

This will apply safe auto-fixes for:
- Unused imports (if any — the `import tomli as tomllib` fallback may or may not be flagged depending on ruff version's dead-code detection)
- Import sorting (isort)
- Pyupgrade modernization (e.g. removing `from typing import...` for types available in 3.12+)

**Verify**: `uv run ruff check` → exit 0, no output (after `--fix`, zero remaining violations)

### Step 3: Run ruff format

```bash
uv run ruff format
```

This reformats all Python files to match the ruff formatter style.

**Verify**: `uv run ruff format --check` → exit 0, no output (confirming already formatted)

### Step 4: Run tests to confirm nothing broke

```bash
uv run pytest
```

**Verify**: All tests pass. If any test fails, inspect the failure — it's likely a formatting change that altered a string used in test assertions. Fix the affected test assertion to match the formatted value, then re-run.

## Test plan

No new tests needed — this plan only adds tooling infrastructure. The existing test suite is the verification.

## Done criteria

Machine-checkable. ALL must hold:

- [ ] `uv run ruff check` exits 0
- [ ] `uv run ruff format --check` exits 0
- [ ] `uv run pytest` exits 0
- [ ] `pyproject.toml` has a `[tool.ruff]` section with the config above
- [ ] `uv run python -c "import tabletop.cli; print('ok')"` prints "ok"
- [ ] No files outside the in-scope list are modified (`git status`)
- [ ] `plans/README.md` status row updated

## STOP conditions

Stop and report back (do not improvise) if:

- The code at the locations in "Current state" doesn't match the excerpts (the codebase has drifted since this plan was written).
- `uv add --dev ruff` fails (network issue or uv version incompatibility).
- `uv run pytest` fails after formatting and the cause is not a trivial string change in a test assertion.
- ruff introduces a change that breaks a non-test module's import resolution (e.g. removing an import that's actually needed at runtime).

## Maintenance notes

- When adding new Python files, run `uv run ruff check --fix && uv run ruff format` before committing.
- The `[tool.ruff.lint.per-file-ignores]` for test files is specific: `N802` (function name should be lowercase), `N803` (argument name should be lowercase), `N806` (variable in function should be lowercase) — test functions and their fixtures use `snake_case` with `test_` prefix, which is PEP 8 compliant. If ruff flags new naming rules, add them to the ignore list instead of renaming tests.
- If the project adds a type checker later (mypy/pyright), make sure the ruff `select` doesn't include `TCH` rules that conflict.
