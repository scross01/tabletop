"""Space-aligned table parser.

Handles separator lines (---...---) between header and data,
and trims trailing non-table lines.
"""

from __future__ import annotations

import re
import sys


class Table:
    """Parsed table with header and typed rows."""

    def __init__(self, header: list[str], rows: list[list[str]]):
        self.header = header
        self.rows = rows
        self._col_widths: list[int] | None = None

    def __len__(self) -> int:
        return len(self.rows)

    def __bool__(self) -> bool:
        return bool(self.header)

    @property
    def ncols(self) -> int:
        return len(self.header)

    @property
    def col_widths(self) -> list[int]:
        if self._col_widths is None:
            self._col_widths = [len(h) for h in self.header]
            for row in self.rows:
                for i, val in enumerate(row):
                    if i < len(self._col_widths):
                        self._col_widths[i] = max(self._col_widths[i], len(val))
        return self._col_widths

    def column_index(self, spec: str) -> int | None:
        if spec.isdigit():
            idx = int(spec) - 1
            return idx if 0 <= idx < self.ncols else None
        lower = spec.lower()
        for i, h in enumerate(self.header):
            if h.lower() == lower:
                return i
        return None

    def column_name(self, spec: str) -> str:
        idx = self.column_index(spec)
        return self.header[idx] if idx is not None else spec

    def copy(self) -> Table:
        return Table(list(self.header), [list(r) for r in self.rows])


def _is_separator(line: str) -> bool:
    """Check if a line is a separator (---...--- or ===...=== etc)."""
    stripped = line.strip()
    if not stripped:
        return False
    compacted = stripped.replace(" ", "").replace("\t", "")
    if len(compacted) < 3:
        return False
    first = compacted[0]
    if first.isalnum():
        return False
    return all(c == first for c in compacted)


def _process_data_rows(
    lines: list[str],
    boundaries: list[int],
    ncols: int,
) -> tuple[list[list[str]], list[str]]:
    """Process data rows, snapping boundaries and detecting trailing lines."""
    rows = []
    trailing = []
    in_table = True
    for line in lines:
        if not in_table:
            trailing.append(line)
            continue
        if _is_separator(line):
            continue
        hints = _find_content_starts(line)
        radius = max(10, min(80, len(line) // max(1, ncols)))
        snapped = [_snap_to_space(line, b, hints, radius=radius) for b in boundaries]
        fields = _split(line, snapped)
        if len(fields) < ncols:
            in_table = False
            trailing.append(line)
            continue
        if _is_aligned(line, boundaries):
            rows.append(fields[:ncols])
            continue
        # Row isn't perfectly aligned — accept it only if the data row
        # has enough 2+ space gaps to plausibly be a table row (at least
        # ncols-1-floor(ncols/2) content-starts) AND boundaries aren't
        # all clustered in a single stretch of whitespace.
        min_hints = max(1, ncols - 1 - ncols // 2)
        too_few_hints = len(hints) < min_hints
        too_close = any(snapped[i] - snapped[i - 1] <= 2 for i in range(1, len(snapped)))
        if too_few_hints or too_close:
            in_table = False
            trailing.append(line)
        else:
            rows.append(fields[:ncols])
    return rows, trailing


def _parse_table_lines(lines: list[str]) -> tuple[list[str], list[list[str]], list[str]]:
    """Parse raw lines into header, rows, and trailing lines."""
    if not lines:
        return [], [], []

    raw = [line.rstrip("\n\r") for line in lines if line.strip()]
    if not raw:
        return [], [], []

    sep_idx = None
    if len(raw) > 1 and _is_separator(raw[1]):
        sep_idx = 1

    data_start = 2 if sep_idx is not None else 1

    if sep_idx is not None:
        boundaries = _boundaries_from_separator(raw[sep_idx])
        header_len = len(raw[0])
        boundaries = [b for b in boundaries if b <= header_len]
        header = _split(raw[0], boundaries)
    else:
        header_starts = _find_content_starts(raw[0])
        # Find the row with the most content-starts — this tells us the
        # true column count when the header uses single spaces between
        # column names (e.g. "Avail Capacity iused ifree %iused").
        data_starts = []
        for line in raw[data_start:]:
            starts = _find_content_starts(line)
            if len(starts) > len(data_starts):
                data_starts = starts
        if len(data_starts) > len(header_starts):
            boundaries = list(header_starts)
            for ds in data_starts:
                if not any(abs(ds - h) <= 3 for h in boundaries):
                    boundaries.append(ds)
            boundaries.sort()
            # Expand merged header column names by splitting on single
            # spaces (e.g. "Avail Capacity iused ifree %iused").
            unmerged = _split(raw[0], header_starts)
            ncols = len(boundaries) + 1
            expanded = []
            for h in unmerged:
                parts = h.split()
                needed = ncols - len(expanded)
                if len(parts) > 1 and len(parts) <= needed:
                    expanded.extend(parts)
                else:
                    expanded.append(h)
            while len(expanded) < ncols:
                expanded.append(f"col{len(expanded) + 1}")
            header = expanded[:ncols]
        else:
            boundaries = header_starts
            header = _split(raw[0], boundaries)

    ncols = len(header)
    rows, trailing = _process_data_rows(raw[data_start:], boundaries, ncols)

    return header, rows, trailing


def _boundaries_from_separator(line: str) -> list[int]:
    """Extract column start positions from a separator line."""
    boundaries = []
    i = 0
    while i < len(line):
        c = line[i]
        if not c.isalnum() and c != " ":
            if i > 0:
                boundaries.append(i)
            j = i
            while j < len(line) and line[j] == c:
                j += 1
            i = j
        else:
            i += 1
    return boundaries


def _find_content_starts(line: str) -> list[int]:
    """Find positions where content starts after a 2+ space gap."""
    starts = []
    i = 0
    while i < len(line):
        if line[i] == " ":
            j = i
            while j < len(line) and line[j] == " ":
                j += 1
            if j - i >= 2 and j < len(line):
                starts.append(j)
            i = j
        else:
            i += 1
    return starts


def _find_column_boundaries(lines: list[str]) -> list[int]:
    """Find column split positions from data lines using 2+ space gaps.

    Uses content-start positions (after a gap) which are more stable
    than gap-start positions when column values have variable widths.
    """
    if not lines:
        return []

    content_starts = []
    for line in lines:
        starts = set(_find_content_starts(line))
        content_starts.append(starts)

    all_positions = sorted({p for s in content_starts for p in s})
    if not all_positions:
        return []

    clusters: list[list[int]] = [[all_positions[0]]]
    for pos in all_positions[1:]:
        if pos - clusters[-1][-1] <= 3:
            clusters[-1].append(pos)
        else:
            clusters.append([pos])

    if len(lines) == 1:
        return [max(c) for c in clusters]

    threshold = max(1, len(lines) // 2)
    boundaries = []
    for cluster in clusters:
        count = sum(1 for s in content_starts if any(p in s for p in cluster))
        if count >= threshold:
            boundaries.append(max(cluster))

    return sorted(boundaries)


def _split(line: str, boundaries: list[int]) -> list[str]:
    """Split a line at boundary positions.

    Preserves empty intermediate fields but trims trailing empty fields.
    """
    if not boundaries:
        return re.split(r"  +", line.strip())
    fields = []
    prev = 0
    for b in boundaries:
        field = line[prev:b].strip()
        fields.append(field)
        prev = b
    field = line[prev:].strip()
    fields.append(field)
    # Trim trailing empty fields
    while fields and not fields[-1]:
        fields.pop()
    return fields


def _snap_to_space(line: str, pos: int, hints: list[int] | None = None, radius: int = 10) -> int:
    """Snap a position to a column boundary in the data line.

    If hints (content-start positions from the data row) are provided and one
    falls within ±3 of pos, use it. Otherwise snap to the nearest space.
    """
    # If a data-row content-start hint is nearby, use the nearest one
    if hints:
        best = None
        best_dist = 4
        for h in hints:
            dist = abs(h - pos)
            if dist < best_dist or (dist == best_dist and h > (best or 0)):
                best_dist = dist
                best = h
        if best is not None:
            return best

    if pos < len(line) and line[pos] == " ":
        return pos

    best = pos
    best_dist = radius + 1

    i = min(pos - 1, len(line) - 1)
    while i >= max(0, pos - radius):
        if i >= 0 and line[i] == " ":
            dist = pos - i
            if dist < best_dist:
                best = i
                best_dist = dist
            break
        i -= 1

    i = pos
    while i < min(len(line), pos + radius + 1):
        if line[i] == " ":
            dist = i - pos
            if dist < best_dist:
                best = i
                best_dist = dist
            break
        i += 1

    return best


def _is_aligned(line: str, boundaries: list[int]) -> bool:
    """Check if a line's fields align with column boundaries.

    Requires all boundaries to fall on whitespace or past end of line.
    """
    if not boundaries:
        return True
    for b in boundaries:
        if b >= len(line):
            continue
        if b == len(line) - 1:
            continue
        if line[b] != " ":
            return False
    return True


def parse(lines: list[str], has_header: bool = True) -> Table:
    """Parse space-aligned input into a Table."""
    if not has_header:
        raw = [line.rstrip("\n\r") for line in lines if line.strip()]
        if not raw:
            return Table([], [])
        boundaries = _find_column_boundaries(raw)
        ncols = len(_split(raw[0], boundaries))
        header = [f"col{i+1}" for i in range(ncols)]
        rows = [_split(line, boundaries) for line in raw]
        return Table(header, rows)

    header, rows, _trailing = _parse_table_lines(lines)
    return Table(header, rows)


def read_input(path: str | None) -> list[str]:
    """Read lines from file or stdin."""
    if path:
        try:
            with open(path) as f:
                return f.readlines()
        except FileNotFoundError:
            print(f"tabletop: {path}: No such file", file=sys.stderr)
            sys.exit(1)
        except IsADirectoryError:
            print(f"tabletop: {path}: Is a directory", file=sys.stderr)
            sys.exit(1)
    if not sys.stdin.isatty():
        return sys.stdin.readlines()
    print("tabletop: reading from stdin (Ctrl+D to end)...", file=sys.stderr)
    return sys.stdin.readlines()
