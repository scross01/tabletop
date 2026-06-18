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

_OUTLINE_LEFT_CHARS = frozenset(
    {
        _OUTLINE_TOP_LEFT,
        _OUTLINE_BOT_LEFT,
        _OUTLINE_MID_LEFT,
        _OUTLINE_HEAD_LEFT,
        _OUTLINE_VERT,
        _OUTLINE_VERT_HEADER,
    }
)
_OUTLINE_RIGHT_CHARS = frozenset(
    {
        _OUTLINE_TOP_RIGHT,
        _OUTLINE_BOT_RIGHT,
        _OUTLINE_MID_RIGHT,
        _OUTLINE_HEAD_RIGHT,
        _OUTLINE_VERT,
        _OUTLINE_VERT_HEADER,
    }
)


def _is_outline_line(line: str) -> bool:
    """Return True if the line is a Unicode box-drawing outline row."""
    stripped = line.strip()
    if not stripped:
        return False
    first = stripped[0]
    last = stripped[-1]
    return first in _OUTLINE_LEFT_CHARS and last in _OUTLINE_RIGHT_CHARS


def _detect_outline_table(lines: list[str], has_header: bool = True) -> bool:
    """Return True if the input appears to be a Unicode outline table.

    Heuristic: scan through lines until we find one starting with the
    top-left corner character (┏).  Non-blank, non-box-drawing lines
    before the top border (e.g. titles) are allowed.  Once the top
    border is found, confirm at least one │ data row exists.
    """
    if not has_header:
        return False
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped[0] == _OUTLINE_TOP_LEFT:
            # Confirm there's at least one │ data row
            return any(_is_outline_line(line) for line in lines)
    return False


def _split_outline_row(line: str) -> list[str]:
    """Split an outline data row (│...│...│) into field values."""
    stripped = line.strip()
    # Remove leading and trailing vertical bars
    if stripped.startswith(_OUTLINE_VERT):
        stripped = stripped[1:]
    if stripped.endswith(_OUTLINE_VERT):
        stripped = stripped[:-1]
    # Split on │ and strip each field
    fields = stripped.split(_OUTLINE_VERT)
    return [f.strip() for f in fields]


def _parse_outline_table(lines: list[str], has_header: bool = True) -> Table:
    """Parse a Unicode box-drawing outline table into a Table.

    Handles formats produced by libraries like Rich, textual, tabulate
    (grid/rounded), etc.  Recognises:
    - Top border: ┏━━┳━━┓
    - Header row: ┃ H1 ┃ H2 ┃
    - Header/data separator: ┡━━╇━━┩ (or ├──┼──┤)
    - Data rows: │ v1 │ v2 │
    - Bottom border: └──┴──┘

    Non-table lines before the top border (e.g. titles) and after the
    bottom border (e.g. summary lines) are ignored.

    ``has_header=False`` causes all │ rows to be treated as data and
    ``col1``/``col2``/… placeholders to be generated for the header.
    """
    header: list[str] = []
    rows: list[list[str]] = []
    found_top = False
    found_bottom = False
    header_done = False

    for line in lines:
        stripped = line.strip()
        if not stripped:
            if found_top and not found_bottom:
                # blank line inside table → treat as end
                found_bottom = True
            continue

        # Detect top border
        if not found_top:
            if stripped[0] == _OUTLINE_TOP_LEFT:
                found_top = True
            continue  # skip the border line itself

        if found_bottom:
            continue

        # Detect bottom border
        if stripped[0] == _OUTLINE_BOT_LEFT:
            found_bottom = True
            continue

        # Skip horizontal separator lines (header separator, mid-table)
        if stripped[0] in (_OUTLINE_HEAD_LEFT, _OUTLINE_MID_LEFT):
            header_done = True
            continue

        # Header row (┃ ... ┃)
        if stripped[0] == _OUTLINE_VERT_HEADER and not header_done:
            if has_header:
                header = _split_outline_row(stripped.replace(_OUTLINE_VERT_HEADER, _OUTLINE_VERT))

        # Data row (│ ... │)
        elif _is_outline_line(stripped):
            fields = _split_outline_row(stripped)
            if has_header:
                if header_done:
                    rows.append(fields)
                elif not header:
                    header = fields
                    header_done = True
            else:
                rows.append(fields)

    if not header and not rows:
        return Table([], [])

    if not header and rows:
        header = [f"col{i + 1}" for i in range(len(rows[0]))]

    ncols = len(header)
    normalized = []
    for row in rows:
        if len(row) == ncols:
            normalized.append(row)
        elif len(row) > ncols:
            normalized.append(row[:ncols])
        else:
            padded = row + [""] * (ncols - len(row))
            normalized.append(padded)

    return Table(header, normalized)
