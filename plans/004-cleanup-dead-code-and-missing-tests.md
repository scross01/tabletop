# Plan 004: Clean up dead code and add missing tests

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md` — unless a reviewer dispatched you and told you they
> maintain the index.
>
> **Drift check (run first)**: `git diff --stat ecfde61..HEAD -- tabletop/cli.py tabletop/parser.py tabletop/outline.py tests/test_parser.py tests/test_cli.py`
> If any in-scope file changed since this plan was written, compare the
> "Current state" excerpts against the live code before proceeding; on a
> mismatch, treat it as a STOP condition.

## Status

- **Priority**: P3
- **Effort**: S
- **Risk**: LOW
- **Depends on**: none
- **Category**: tech-debt / tests
- **Planned at**: commit `ecfde61`, 2026-06-18

## Why this matters

Two pieces of dead code and two untested error paths. None are dangerous on
their own, but dead code accumulates (confuses readers, wastes coverage
metrics), and the untested paths (`read_input` latin-1 fallback, `resolve_output`
multiple-format error) are error-recovery logic that users hit in edge cases.
Cleaning them is minutes of work each.

## Current state

### Dead code 1: `tomli` fallback in `_get_version`

`cli.py:24-27`:
```python
    try:
        import tomllib
    except ImportError:
        import tomli as tomllib
```

`pyproject.toml` requires `python >= 3.12`. `tomllib` has been in the Python
standard library since 3.11. The `except ImportError` branch can never execute.
Remove the try/except and just `import tomllib` directly.

### Dead code 2: `_OUTLINE_HEAD_MID` constant

Either `tabletop/parser.py:86` or `tabletop/outline.py` (if plan 003 has
been applied) contains:
```python
_OUTLINE_HEAD_MID = "╇"
```

This constant is never referenced anywhere in the codebase — it was added
for completeness but `_OUTLINE_HEAD_MID` is not used by the outline table
parser. Remove the line.

### Missing test 1: `read_input` latin-1 fallback

`parser.py:844-850`:
```python
def read_input(path: str | None) -> list[str]:
    if path:
        try:
            with open(path, encoding="utf-8") as f:
                return f.readlines()
        except UnicodeDecodeError:
            with open(path, encoding="latin-1") as f:
                return f.readlines()
```

When a file is not valid UTF-8, the function falls back to latin-1. There is
no test for this branch. Following the pattern from `test_parser.py:249-267`
(`TestReadInput` class), add a test that writes a file containing bytes that
are invalid UTF-8 but valid latin-1 and verifies it reads without error.

### Missing test 2: `resolve_output` multiple-format error

`cli.py:157-159`:
```python
    if len(chosen) > 1:
        print("tabletop: only one output format allowed", file=sys.stderr)
        sys.exit(1)
```

When the user passes multiple output format flags (e.g. `--csv --json`),
the tool prints an error and exits with code 1. No test covers this.
Following the pattern from `test_cli.py:131-138` (`test_head_negative_rejected`),
add a test that passes conflicting format flags and asserts non-zero exit code.

## Commands you will need

| Purpose               | Command                       | Expected on success |
|-----------------------|-------------------------------|---------------------|
| Tests                 | `uv run pytest`               | all pass            |
| Ruff lint             | `uv run ruff check`           | exit 0              |
| Ruff format           | `uv run ruff format --check`  | exit 0              |

## Scope

**In scope** (the only files you should modify):
- `tabletop/cli.py` — remove `tomli` fallback
- `tabletop/parser.py` OR `tabletop/outline.py` — remove `_OUTLINE_HEAD_MID` (whichever file contains it)
- `tests/test_parser.py` — add latin-1 fallback test
- `tests/test_cli.py` — add multiple-format error test

**Out of scope** (do NOT touch):
- `tabletop/transforms.py` — unchanged
- `tabletop/output.py` — unchanged
- Any other test file
- Any fixture file

## Git workflow

- Branch: `advisor/004-cleanup-dead-code-and-missing-tests`
- Commit style: conventional commits
- Two commits: (1) `chore: remove dead code (tomli fallback, unused constant)`, (2) `test: add missing latin-1 and format-conflict tests`
- Do NOT push or open a PR unless instructed

## Steps

### Step 1: Remove `tomli` fallback from `cli.py`

Replace `cli.py:24-27` (the try/except block) with a direct import:

```python
# Old:
    try:
        import tomllib
    except ImportError:
        import tomli as tomllib

# New:
    import tomllib
```

Then remove `import tomli as tomllib` from any imports at the top of the
file if ruff's `--fix` didn't already catch it (it's an inline import, not
a top-level import, so no top-level import to remove).

**Verify**: `uv run python -c "from tabletop.cli import _get_version; v = _get_version(); print(v)"` → prints a version string like "0.2.0"

**Verify**: `uv run ruff check` → exit 0 (ruff's F401 rule would flag an unused `import tomli` if one existed)

### Step 2: Remove `_OUTLINE_HEAD_MID` constant

Find which file contains the dead constant:

```bash
grep -rn '_OUTLINE_HEAD_MID' tabletop/
```

Two possible outcomes:
- Found in `tabletop/parser.py` — plan 003 has not been applied yet. Remove the line.
- Found in `tabletop/outline.py` — plan 003 has been applied. Remove the line from `outline.py`.
- Not found — already removed (skip this step).

Remove the line containing `_OUTLINE_HEAD_MID = "╇"` from the file where
it's found. Do not remove any other lines.

**Verify**: `grep -rn '_OUTLINE_HEAD_MID' tabletop/` → no matches

**Verify**: `uv run python -c "from tabletop.parser import parse; print('ok')"` → prints "ok"
(Also test `from tabletop.outline` if `outline.py` exists)

**Verify**: `uv run pytest` → all tests pass

### Step 3: Add latin-1 fallback test to `test_parser.py`

Add a new test method to the existing `TestReadInput` class in
`tests/test_parser.py` (after `test_read_directory`, before the class ends).
The existing test class looks like:

```python
class TestReadInput:
    def test_read_file(self):
        ...
    def test_read_missing_file(self):
        ...
    def test_read_directory(self):
        ...
```

Add this test:

```python
    def test_read_latin1_fallback(self):
        """File with latin-1 (not valid UTF-8) should read successfully."""
        import tempfile
        from pathlib import Path
        # Latin-1 byte 0xe9 = 'é', which is invalid UTF-8 on its own
        content = b"NAME\xe9\nvalue\n"
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(content)
            path = f.name
        try:
            lines = read_input(path)
            assert len(lines) == 2
            assert "NAME" in lines[0]
        finally:
            Path(path).unlink()
```

Note: `0xe9` is the latin-1 encoding of `é`. In UTF-8, multi-byte sequences
start with a lead byte; a bare `0xe9` byte followed by a non-continuation
byte (here `\n`) is invalid UTF-8 and will trigger `UnicodeDecodeError`,
exercising the fallback.

Place this test after `test_read_directory` and before the class-indentation
gap before `TestOutlineDetection`.

**Verify**: `uv run pytest -v tests/test_parser.py::TestReadInput::test_read_latin1_fallback` → PASSED

### Step 4: Add multiple-format conflict test to `test_cli.py`

Add a new top-level function (not inside a class) to `tests/test_cli.py`,
after `test_tail_negative_rejected` (line 138):

```python
def test_conflicting_formats_rejected():
    r = run_tabletop("--csv", "--json", input_data=SAMPLE)
    assert r.returncode != 0
```

This follows the same pattern as the existing `test_head_negative_rejected`
and `test_tail_negative_rejected`.

**Verify**: `uv run pytest -v tests/test_cli.py::test_conflicting_formats_rejected` → PASSED

### Step 5: Run full verification

```bash
uv run ruff check
uv run ruff format --check
uv run pytest
```

**Verify**: All three exit 0.

## Test plan

Two new tests (no modification to existing tests):

| Test | File | What it covers |
|------|------|----------------|
| `TestReadInput::test_read_latin1_fallback` | `tests/test_parser.py` | `read_input` successfully reads latin-1 encoded file when UTF-8 fails |
| `test_conflicting_formats_rejected` | `tests/test_cli.py` | `resolve_output` exits with error when multiple output formats given |

Both follow existing test patterns in the same files.

## Done criteria

Machine-checkable. ALL must hold:

- [ ] `grep -n 'import tomli' tabletop/cli.py` returns no matches (the except branch and import are removed)
- [ ] `grep -rn '_OUTLINE_HEAD_MID' tabletop/` returns no matches
- [ ] `uv run pytest -v tests/test_parser.py::TestReadInput::test_read_latin1_fallback` exits 0
- [ ] `uv run pytest -v tests/test_cli.py::test_conflicting_formats_rejected` exits 0
- [ ] `uv run ruff check` exits 0
- [ ] `uv run ruff format --check` exits 0
- [ ] `uv run pytest` exits 0 (all tests pass)
- [ ] No files outside the in-scope list are modified (`git status`)
- [ ] `plans/README.md` status row updated

## STOP conditions

Stop and report back (do not improvise) if:

- The code at the locations in "Current state" doesn't match the excerpts (the codebase has drifted since this plan was written).
- `grep -rn '_OUTLINE_HEAD_MID' tabletop/` returns multiple matches — means the constant is actually used somewhere; investigate and report.
- The latin-1 test file write doesn't reliably trigger `UnicodeDecodeError` (unlikely on Python 3.12+, but if the platform uses a UTF-8 mode that changes file-reading behavior, the test won't exercise the fallback). Verify: the bytes `b"NAME\xe9\n"` should be invalid UTF-8 on any standard Python 3.12+ build. If the test passes without exercising the except branch, add a comment documenting the assumption.
- `test_conflicting_formats_rejected` fails (e.g. the `subprocess.run` timeout is too low for the test machine). Increase the timeout in `run_tabletop` or use `input_data=""` instead of `SAMPLE`.

## Maintenance notes

- If Python's minimum supported version ever goes below 3.11, the `import tomllib` direct import would need to be reverted to a try/except fallback. Until then, direct import is correct.
- The latin-1 fallback test uses a raw latin-1 byte (`0xe9`) to trigger the `UnicodeDecodeError`. This is a brittle approach if Python changes its default encoding behavior — if the test starts passing without exercising the fallback, check whether the file content would still be invalid UTF-8.
- If plan 003 (extract outline parser) is applied before this plan, the `_OUTLINE_HEAD_MID` removal in step 2 will find it in `tabletop/outline.py` instead of `tabletop/parser.py` — the plan handles both cases.
