# Plan 003: Extract Unicode outline table parser from parser.py

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md` — unless a reviewer dispatched you and told you they
> maintain the index.
>
> **Drift check (run first)**: `git diff --stat ecfde61..HEAD -- tabletop/parser.py tabletop/ tests/test_parser.py`
> If any in-scope file changed since this plan was written, compare the
> "Current state" excerpts against the live code before proceeding; on a
> mismatch, treat it as a STOP condition.

## Status

- **Priority**: P2
- **Effort**: M
- **Risk**: MED
- **Depends on**: none
- **Category**: tech-debt
- **Planned at**: commit `ecfde61`, 2026-06-18

## Why this matters

`parser.py` is 854 lines (~47% of all source code), handling four distinct
concerns: space-aligned table parsing, Unicode box-drawing (outline) table
parsing, single-space quote-aware parsing, and column boundary detection.
The outline table support (lines 67–226) is fully self-contained — it has its
own constants, helper functions, and parser. Extracting it into a dedicated
module makes the codebase easier to navigate, reduces merge conflict surface,
and establishes a pattern for future parser extraction (e.g. the single-space
parser is another candidate).

## Current state

`tabletop/parser.py` lines 67–226 contain all Unicode outline support:

```python
# parser.py:67-226 (excerpt: constants)
_OUTLINE_TOP_LEFT = "┏"
_OUTLINE_TOP_RIGHT = "┓"
# ... 13 more constants ...

_OUTLINE_LEFT_CHARS = frozenset({...})
_OUTLINE_RIGHT_CHARS = frozenset({...})
```

```python
# parser.py:98-105 (excerpt: helper)
def _is_outline_line(line: str) -> bool:
    """Return True if the line is a Unicode box-drawing outline row."""
    stripped = line.strip()
    if not stripped:
        return False
    first = stripped[0]
    last = stripped[-1]
    return first in _OUTLINE_LEFT_CHARS and last in _OUTLINE_RIGHT_CHARS
```

```python
# parser.py:108-125 (excerpt: detection)
def _detect_outline_table(lines: list[str], has_header: bool = True) -> bool:
    ...
```

```python
# parser.py:128-138 (excerpt: row splitter)
def _split_outline_row(line: str) -> list[str]:
    ...
```

```python
# parser.py:141-225 (excerpt: main parser)
def _parse_outline_table(lines: list[str], has_header: bool = True) -> Table:
    ...
```

The `parse()` function in `parser.py:790-794` uses these functions:

```python
# parser.py:790-794
def parse(lines: list[str], has_header: bool = True) -> Table:
    # Try Unicode box-drawing (outline) table first
    if _detect_outline_table(lines, has_header):
        return _parse_outline_table(lines, has_header)
```

The `Table` class is defined in `parser.py:16-65` — it's used by both the
space-aligned and outline parsers. This plan keeps `Table` in `parser.py`
and uses a strategically placed import to avoid circular dependencies (see
step 2 for the pattern).

Convention to match (from `parser.py:8-13`):
```python
from __future__ import annotations

import bisect
import re
import sys
from collections import Counter
```

Test imports that will need updating (`test_parser.py:275`):
```python
from tabletop.parser import _detect_outline_table
```

## Commands you will need

| Purpose               | Command                       | Expected on success |
|-----------------------|-------------------------------|---------------------|
| Tests                 | `uv run pytest`               | all pass            |
| Ruff lint             | `uv run ruff check`           | exit 0              |
| Ruff format           | `uv run ruff format --check`  | exit 0              |

## Scope

**In scope** (the only files you should modify):
- `tabletop/outline.py` — create this file
- `tabletop/parser.py` — remove outline code, add import
- `tests/test_parser.py` — update import source for outline tests

**Out of scope** (do NOT touch):
- `tabletop/transforms.py` — unchanged
- `tabletop/output.py` — unchanged
- `tabletop/cli.py` — unchanged
- `tests/conftest.py` — unchanged (fixtures use `parse()`, which still works)
- `tests/test_fixtures.py` — unchanged
- Any file outside `tabletop/outline.py`, `tabletop/parser.py`, `tests/test_parser.py`

## Git workflow

- Branch: `advisor/003-extract-outline-table-parser`
- Commit style: conventional commits
- One commit: `refactor(parser): extract outline table parser into tabletop/outline.py`
- Do NOT push or open a PR unless instructed

## Steps

### Step 1: Create `tabletop/outline.py`

Create `tabletop/outline.py` with the following content patterns.

**Module docstring and imports** — use the same conventions as other modules
(`from __future__ import annotations`, no unused imports):

```python
"""Unicode box-drawing (outline) table parser.

Handles formats produced by Rich, textual, tabulate (grid/rounded), etc.
"""

from __future__ import annotations

from .parser import Table


_OUTLINE_TOP_LEFT = "┏"
_OUTLINE_TOP_RIGHT = "┓"
_OUTLINE_TOP_MID = "┳"
_OUTLINE_BOT_LEFT = "└"
_OUTLINE_BOT_RIGHT = "┘"
_OUTLINE_BOT_MID = "┴"
_OUTLINE_VERT = "│"
_OUTLINE_VERT_HEADER = "┃"
_OUTLINE_HORIZ = "━"
_OUTLINE_HORIZ_DATA = "─"
_OUTLINE_MID_LEFT = "├"
_OUTLINE_MID_RIGHT = "┤"
_OUTLINE_MID_MID = "┼"
_OUTLINE_HEAD_LEFT = "┡"
_OUTLINE_HEAD_RIGHT = "┩"

_OUTLINE_LEFT_CHARS = frozenset({
    _OUTLINE_TOP_LEFT, _OUTLINE_BOT_LEFT, _OUTLINE_MID_LEFT,
    _OUTLINE_HEAD_LEFT, _OUTLINE_VERT, _OUTLINE_VERT_HEADER,
})
_OUTLINE_RIGHT_CHARS = frozenset({
    _OUTLINE_TOP_RIGHT, _OUTLINE_BOT_RIGHT, _OUTLINE_MID_RIGHT,
    _OUTLINE_HEAD_RIGHT, _OUTLINE_VERT, _OUTLINE_VERT_HEADER,
})
```

Then copy the following functions verbatim from `parser.py` (matching the
code exactly — no edits except removing `_OUTLINE_HEAD_MID` which is dead
code):

- `_is_outline_line` (parser.py lines 98–105)
- `_detect_outline_table` (parser.py lines 108–125)
- `_split_outline_row` (parser.py lines 128–138)
- `_parse_outline_table` (parser.py lines 141–225)

Note: `_parse_outline_table` uses `Table` — the import at the top of
`outline.py` (`from .parser import Table`) supplies it. Do NOT change the
function signature or body.

Do NOT include `_OUTLINE_HEAD_MID` (parser.py line 86) — it's unused.

**Verify**: `uv run python -c "from tabletop.outline import _detect_outline_table, _parse_outline_table; print('ok')"` → prints "ok"

### Step 2: Add re-export import in `parser.py`

In `parser.py`, add the import from `outline` BELOW the `Table` class
definition (after line 65) and BEFORE the `_is_separator` function
which starts the space-aligned parsing section. The `Table` class must
be defined before `outline.py` tries to import it.

Insert after line 65 (`return Table(list(self.header), [list(r) for r in self.rows])` — the blank line after the class):

```python
# ── Unicode outline table support ──────────────────────────────
from .outline import _detect_outline_table, _parse_outline_table
```

**Verify**: `uv run python -c "from tabletop.parser import parse; print('ok')"` → prints "ok"

### Step 3: Remove the outline code from `parser.py`

Delete lines 67 through 226 from `parser.py` — this is everything from the
comment `# ── Unicode box-drawing (outline) table support ──────` through
the end of `_parse_outline_table`. The exact deletion boundary:

- Start: delete line 67 (`# ── Unicode box-drawing (outline) table support ──────`)
- End: delete line 226 (the closing blank line after `_parse_outline_table`'s `return Table(header, normalized)`)

After deletion, verify the file structure is:
1. Imports + `Table` class (lines 1–65)
2. The new import line you added in step 2
3. Separator detection functions (`_is_separator`, lines 228–242)
4. The rest of the space-aligned parser unchanged

**Verify**: `uv run python -c "from tabletop.parser import parse, read_input; print('ok')"` → prints "ok"

**Verify**: `uv run pytest` → all tests pass (some may fail — continue to step 4)

### Step 4: Update test imports in `test_parser.py`

The `TestOutlineDetection` class imports `_detect_outline_table` from
`tabletop.parser` inline (e.g. `test_parser.py:275`). Change each such
import to reference `tabletop.outline` instead:

```python
# Old:
from tabletop.parser import _detect_outline_table
# New:
from tabletop.outline import _detect_outline_table
```

There are four occurrences in `test_parser.py` (lines 275, 289, 303, 313).
Use search-and-replace or change each one.

`TestOutlineParsing` uses `parse()` directly, not the outline functions —
no change needed.

**Verify**: `grep -n 'from tabletop.parser import _detect' tests/test_parser.py` → no matches

**Verify**: `uv run pytest -v tests/test_parser.py::TestOutlineDetection tests/test_parser.py::TestOutlineParsing` → all outline tests pass

### Step 5: Run full verification

```bash
uv run ruff check
uv run ruff format --check
uv run pytest
```

**Verify**: All three exit 0.

## Test plan

No new tests needed. The existing test suite covers:
- `TestOutlineDetection` (4 tests) — verifies `_detect_outline_table` works correctly
- `TestOutlineParsing` (6 tests) — verifies `_parse_outline_table` via `parse()`
- `test_hermes_skills_*` in `test_fixtures.py` (7 tests) — verifies real-world outline table parsing end-to-end

All of these pass through the extracted module without behavior change.

## Done criteria

Machine-checkable. ALL must hold:

- [ ] `tabletop/outline.py` exists with all outline constants and functions
- [ ] `tabletop/parser.py` no longer contains any outline-specific code (no `_OUTLINE_*` constants, no `_is_outline_line`, no `_detect_outline_table`, no `_split_outline_row`, no `_parse_outline_table`)
- [ ] `tabletop/parser.py` imports `_detect_outline_table` and `_parse_outline_table` from `.outline`
- [ ] `grep -rn '_OUTLINE_\|_is_outline_line\|_detect_outline_table\|_split_outline_row\|_parse_outline_table' tabletop/parser.py` returns no matches
- [ ] `grep -n 'from tabletop.parser import _detect' tests/test_parser.py` returns no matches
- [ ] `uv run ruff check` exits 0
- [ ] `uv run ruff format --check` exits 0
- [ ] `uv run pytest` exits 0 (all tests pass)
- [ ] No files outside the in-scope list are modified (`git status`)
- [ ] `plans/README.md` status row updated

## STOP conditions

Stop and report back (do not improvise) if:

- The code at the locations in "Current state" doesn't match the excerpts (the codebase has drifted since this plan was written).
- `uv run python -c "from tabletop.parser import parse, Table; print('ok')"` fails with an `ImportError` — this indicates a circular import problem. If so, verify that the `from .outline import ...` line was placed AFTER the `Table` class definition in `parser.py`.
- `uv run pytest` fails on tests unrelated to outline parsing — investigate, but do not fix unrelated failures as part of this plan.
- Removing `_OUTLINE_HEAD_MID` causes a `NameError` — if so (unlikely, confirm it's dead with `grep`), it means another function uses it; restore the constant.

## Maintenance notes

- If a new outline table variant needs to be supported (e.g. a different box-drawing character set), the change is isolated to `tabletop/outline.py`.
- The `parser.py` file is still large (~630 lines after extraction). Future plans could extract the single-space quote-aware parser (`_split_whitespace_with_quotes`, `_try_parse_single_space`) into a dedicated module as well.
- The `from .parser import Table` in `outline.py` is a cross-module dependency but not a circular one, as long as the import in `parser.py` is placed after `Table`'s definition and `outline.py` only uses `Table` by name (not during module initialization). If `outline.py` ever needs to reference `Table` at module level (not inside a function), the import placement in `parser.py` must remain correct.
