# Plan 002: Add GitHub Actions CI

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md` — unless a reviewer dispatched you and told you they
> maintain the index.
>
> **Drift check (run first)**: `git diff --stat ecfde61..HEAD -- .github/`
> AND verify plan 001 is DONE (ruff is configured). If `ruff check` or
> `ruff format --check` fails, stop and complete plan 001 first.

## Status

- **Priority**: P1
- **Effort**: S
- **Risk**: LOW
- **Depends on**: plans/001-add-ruff-linter.md (ruff must be installed and passing)
- **Category**: dx
- **Planned at**: commit `ecfde61`, 2026-06-18

## Why this matters

Every pull request and push to the default branch runs untested. There is no
CI pipeline. Adding a GitHub Actions workflow gives automated verification that:
(1) tests pass, (2) ruff lint rules are satisfied, (3) code is formatted
correctly. This catches regressions before they land on `main`.

## Current state

- No `.github/` directory exists.
- No CI configuration anywhere in the repo.
- The `Makefile` only wraps `vhs` for demo GIF generation — no test or lint targets.
- Package manager is `uv` (via `uv.lock` and `pyproject.toml`).
- Python version is pinned to 3.12 in `.python-version`.
- Tests run with `uv run pytest`.
- Lint runs with `uv run ruff check` (after plan 001).
- Format check runs with `uv run ruff format --check` (after plan 001).

## Commands you will need

| Purpose               | Command                       | Expected on success |
|-----------------------|-------------------------------|---------------------|
| Validate workflow     | `uv run python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))"` | no error |
| Verify tests locally  | `uv run pytest`               | all pass            |
| Verify ruff locally   | `uv run ruff check && uv run ruff format --check` | exit 0              |

Note: GitHub Actions does not have a local dry-run mode. The workflow must be
pushed to a branch and a PR opened for GitHub to parse and run it. If `act`
(Docker-based local runner) is available, use it for pre-push validation;
otherwise verify syntax via the Python YAML check above.

## Scope

**In scope** (the only files you should modify):
- `.github/workflows/ci.yml` — create this file

**Out of scope** (do NOT touch):
- Any Python source file, test file, or config file
- `Makefile` — not part of CI
- The `demo` target or anything related to demo GIF generation

## Git workflow

- Branch: `advisor/002-add-github-actions-ci`
- Commit style: conventional commits
- One commit: `ci: add GitHub Actions workflow for tests and lint`
- Do NOT push or open a PR unless instructed

## Steps

### Step 1: Create the CI workflow

Create `.github/workflows/ci.yml` with the following content:

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.12", "3.13"]

    steps:
      - uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v5
        with:
          python-version: ${{ matrix.python-version }}

      - name: Install dependencies
        run: uv sync --dev

      - name: Lint
        run: uv run ruff check

      - name: Check formatting
        run: uv run ruff format --check

      - name: Test
        run: uv run pytest
```

Notes on the workflow:
- Uses `astral-sh/setup-uv` (the official uv GitHub Action) to install uv and the correct Python version — this is the standard approach as of 2025+. If the action version (`v5`) is outdated, use the latest available version.
- Tests on both Python 3.12 (minimum supported) and 3.13 (latest stable).
- Runs lint, format check, and tests as three separate steps so each one's output is visible independently.
- `uv sync --dev` installs both runtime and dev dependencies (including pytest and ruff).

**Verify**: `python3 -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))"` → no error. If `yaml` is not available, install it (`pip install pyyaml`) or use this simpler check:

```bash
python3 -c "
import re
with open('.github/workflows/ci.yml') as f:
    content = f.read()
# Check basic structural elements are present
assert 'on:' in content, 'Missing trigger section'
assert 'jobs:' in content, 'Missing jobs section'
assert 'actions/checkout' in content, 'Missing checkout step'
assert 'astral-sh/setup-uv' in content, 'Missing uv setup'
assert 'ruff check' in content, 'Missing ruff lint step'
assert 'ruff format --check' in content, 'Missing ruff format step'
assert 'pytest' in content, 'Missing pytest step'
print('Workfile structure looks correct')
"
```

### Step 2: Run the build to confirm no regressions

Run the local verification commands that CI will use:

```bash
uv run ruff check
uv run ruff format --check
uv run pytest
```

**Verify**: All three commands exit 0.

## Test plan

No new tests — this plan adds CI infrastructure only. The existing pytest suite
and ruff configuration are the verification.

## Done criteria

Machine-checkable. ALL must hold:

- [ ] `.github/workflows/ci.yml` exists and is valid YAML
- [ ] `uv run ruff check` exits 0
- [ ] `uv run ruff format --check` exits 0
- [ ] `uv run pytest` exits 0
- [ ] No files outside the in-scope list are modified (`git status`)
- [ ] `plans/README.md` status row updated

## STOP conditions

Stop and report back (do not improvise) if:

- `uv run ruff check` or `uv run ruff format --check` fails — this plan depends on plan 001 (ruff). If plan 001 isn't DONE, stop.
- `uv run pytest` fails — the CI won't pass until tests are fixed.
- `astral-sh/setup-uv@v5` doesn't exist at the specified tag. If so, check the latest version at https://github.com/astral-sh/setup-uv/releases and use the latest stable release tag. Do NOT use `@main` or `@master`.

## Maintenance notes

- When adding new dev dependencies, `uv sync --dev` in CI will pick them up automatically.
- If a new Python feature requires a version >3.12, update both `.python-version` and the CI matrix.
- The workflow matrix includes 3.13 as a "latest stable" check. When 3.14 is released, add it and the oldest supported should stay at 3.12 until `requires-python` in `pyproject.toml` changes.
- If a future plan adds other verification steps (e.g., `mypy`, `pytest-cov`), add them as additional steps in the `test` job.
