"""Space-aligned table parser.

Handles separator lines (---...---) between header and data,
and trims trailing non-table lines.
"""

from __future__ import annotations

import bisect
import re
import sys
from collections import Counter


class Table:
    """Parsed table with header and typed rows.

    ``header`` and ``rows`` are treated as immutable after construction.
    Mutating them externally will corrupt the cached ``col_widths``.
    Use ``copy()`` to create a mutable duplicate.
    """

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
    *,
    word_expanded: bool = False,
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
        # Fast path: boundaries already fall on spaces — split directly
        # without snapping, which can create duplicate positions for
        # single-space-separated columns (e.g. ``ps -eaf``).
        if _is_aligned(line, boundaries):
            fields = _split(line, boundaries)
            if len(fields) >= ncols:
                rows.append(fields[:ncols])
                continue

        # Try per-row word-start boundaries when the header was
        # expanded via word analysis (i.e. some columns are separated
        # by single spaces).  Each row's own word starts naturally
        # align with spaces, giving correct column splits.
        hints = _find_content_starts(line)
        if word_expanded and len(hints) + 1 < ncols:
            word_starts = _find_word_starts(line)
            if len(word_starts) >= ncols:
                row_boundaries = [ws - 1 for ws in word_starts[1:ncols]]
                if _is_aligned(line, row_boundaries):
                    fields = _split(line, row_boundaries)
                    if len(fields) >= ncols:
                        rows.append(fields[:ncols])
                        continue

        radius = max(10, min(80, len(line) // max(1, ncols)))
        snapped = [_snap_to_space(line, b, hints, radius=radius) for b in boundaries]
        fields = _split(line, snapped)
        if len(fields) < ncols:
            in_table = False
            trailing.append(line)
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
    expanded_via_words = False

    if sep_idx is not None:
        boundaries = _boundaries_from_separator(raw[sep_idx])
        header_len = len(raw[0])
        boundaries = [b for b in boundaries if b <= header_len]
        header = _split(raw[0], boundaries)
    else:
        header_starts = _find_content_starts(raw[0])
        data_lines = raw[data_start:]

        # Find the row with the most 2+ space gap starts in data
        data_starts: list[int] = []
        for line in data_lines:
            starts = _find_content_starts(line)
            if len(starts) > len(data_starts):
                data_starts = starts

        gap_cols = len(header_starts) + 1

        # Quick pre-check: only run expensive word-start clustering if
        # any data row has more words than the header's gap columns.
        data_word_clusters: list[int] = []
        word_cols = gap_cols
        for line in data_lines:
            wc = len(line.split())
            if wc > word_cols:
                word_cols = wc
            if word_cols > gap_cols:
                data_word_clusters = _cluster_word_starts_by_rank(data_lines)
                word_cols = len(data_word_clusters)
                break

        # Decide whether to expand the header beyond the 2+-space-gap
        # boundaries.  Three strategies, tried in priority order:
        #
        # 1. Word-start clusters suggest *more* columns than header gaps,
        #    AND the header has enough individual words to reach that
        #    count → split multi-word header fields.
        #
        # 2. Data has more 2+ space gaps than the header (existing
        #    behaviour for headers like "Avail Capacity iused ifree").
        #
        # 3. Fall back to header gaps only.
        expanded_via_words = False
        if word_cols > gap_cols:
            unmerged = _split(raw[0], header_starts)
            total_header_words = sum(
                len(h.split()) for h in unmerged if h
            )
            if total_header_words >= word_cols:
                _boundaries, header = _expand_header_for_data_columns(
                    raw[0], header_starts, data_word_clusters
                )
                boundaries = _boundaries
                expanded_via_words = True
            elif (
                total_header_words == word_cols - 1
                and len(data_word_clusters) > total_header_words
            ):
                # Header has one fewer word than data word clusters
                # (e.g. lsof's trailing "(LISTEN)" adds an extra word).
                # Use the header word count as the column target and
                # derive boundaries from the corresponding word clusters.
                capped = data_word_clusters[:total_header_words]
                _boundaries, header = _expand_header_for_data_columns(
                    raw[0], header_starts, capped
                )
                boundaries = _boundaries
                expanded_via_words = True

        if not expanded_via_words:
            if len(data_starts) > len(header_starts):
                boundaries = list(header_starts)
                for ds in data_starts:
                    if not any(abs(ds - h) <= 3 for h in boundaries):
                        boundaries.append(ds)
                boundaries.sort()
                unmerged = _split(raw[0], header_starts)
                ncols = len(boundaries) + 1
                header = _split_header_fields(unmerged, ncols)
            else:
                boundaries = header_starts
                header = _split(raw[0], boundaries)

    ncols = len(header)
    rows, trailing = _process_data_rows(raw[data_start:], boundaries, ncols, word_expanded=expanded_via_words)

    return header, rows, trailing


def _split_header_fields(unmerged: list[str], target_cols: int) -> list[str]:
    """Split multi-word header fields to reach *target_cols*.

    When the total word count across all non-empty fields exactly matches
    *target_cols*, all multi-word fields are split unconditionally
    (handles cases like ``"PID TTY"`` → ``["PID","TTY"]``).  When it
    exceeds, a conservative approach preserves multi-word names like
    ``"Mounted on"``.

    Leading empty fields (artifact of right-aligned first columns) are
    stripped, and missing columns are padded with ``colN`` placeholders.
    """
    non_empty = [h for h in unmerged if h]
    total_words = sum(len(h.split()) for h in non_empty)

    if total_words == target_cols:
        # Perfect match — split all multi-word fields unconditionally
        expanded: list[str] = []
        for h in unmerged:
            parts = h.split()
            if len(parts) > 1:
                expanded.extend(parts)
            else:
                expanded.append(h)
    else:
        # Conservative — split only if there is room
        expanded = []
        for h in unmerged:
            parts = h.split()
            needed = target_cols - len(expanded)
            if len(parts) > 1 and len(parts) <= needed:
                expanded.extend(parts)
            else:
                expanded.append(h)

    # Remove leading empty fields
    while expanded and not expanded[0]:
        expanded.pop(0)

    while len(expanded) < target_cols:
        expanded.append(f"col{len(expanded) + 1}")

    return expanded[:target_cols]


def _expand_header_for_data_columns(
    header_line: str,
    header_gap_starts: list[int],
    data_word_clusters: list[int],
) -> tuple[list[int], list[str]]:
    """Build expanded header and boundaries when data reveals extra columns.

    Uses :func:`_split_header_fields` to split multi-word header fields
    and data word-start clusters as column boundaries for data rows.

    Returns ``(boundaries, header)``.
    """
    unmerged = _split(header_line, header_gap_starts)
    target_cols = len(data_word_clusters)
    header = _split_header_fields(unmerged, target_cols)

    # Use the gap just before each word-start cluster as a boundary
    # (skip the first cluster — it's the start of column 1, not a
    # boundary between columns).  Subtracting 1 converts a word-start
    # position to the space character that precedes it, which ensures
    # ``_is_aligned`` passes and the row is accepted directly.
    boundaries = [c - 1 for c in data_word_clusters[1:]] if len(data_word_clusters) > 1 else []
    return boundaries, header


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


def _find_word_starts(line: str) -> list[int]:
    """Find all positions where a word (non-space) starts.

    This includes position 0 if the line starts with non-space,
    and any position where a non-space character follows a space.
    Unlike ``_find_content_starts``, this does not require 2+ space gaps.
    """
    if not line:
        return []
    starts: list[int] = []
    if line[0] != " ":
        starts.append(0)
    for i in range(1, len(line)):
        if line[i] != " " and line[i - 1] == " ":
            starts.append(i)
    return starts


def _cluster_word_starts_by_rank(lines: list[str]) -> list[int]:
    """Cluster word-start positions by rank (column index) across data rows.

    Unlike position-based clustering, this pairs the *k*-th word start
    in each row, which handles variable-width columns where absolute
    positions shift by row.  Returns the median position for each rank.

    Only rows with the most common word count are considered, avoiding
    trailing summary lines skewing the result.
    """
    if not lines:
        return []

    # Collect word starts per row
    row_starts: list[list[int]] = []
    for line in lines:
        if not line.strip():
            continue
        starts = _find_word_starts(line)
        if starts:
            row_starts.append(starts)

    if not row_starts:
        return []

    # Use only rows with the modal word count (exclude trailing noise)
    wc_counts = Counter(len(s) for s in row_starts)
    modal_count = wc_counts.most_common(1)[0][0]
    filtered = [s for s in row_starts if len(s) == modal_count]

    # For each rank, collect all positions and take median
    clusters: list[int] = []
    for rank in range(modal_count):
        positions = sorted(s[rank] for s in filtered if rank < len(s))
        if positions:
            mid = len(positions) // 2
            if len(positions) % 2 == 0:
                # True median: average the two middle values for even-length
                # arrays.  Using the larger outright (as floor division does)
                # biases boundaries toward rows with wider columns, which
                # can cause snapping failures with few rows.
                clusters.append((positions[mid - 1] + positions[mid]) // 2)
            else:
                clusters.append(positions[mid])

    return clusters


def _split_whitespace_with_quotes(line: str) -> list[str]:
    """Split a line on whitespace, treating quoted strings as single tokens.

    Handles both single (``'...'``) and double (``"..."``) quotes.
    Unmatched quotes are treated as literal characters.
    """
    fields: list[str] = []
    current: list[str] = []
    in_quote: str | None = None
    for c in line:
        if in_quote:
            if c == in_quote:
                in_quote = None
            else:
                current.append(c)
        elif c in ('"', "'"):
            if current:
                fields.append("".join(current))
                current = []
            in_quote = c
        elif c in (" ", "\t"):
            if current:
                fields.append("".join(current))
                current = []
        else:
            current.append(c)
    if current:
        fields.append("".join(current))
    return fields


def _try_parse_single_space(lines: list[str]) -> list[list[str]] | None:
    """Try to parse lines as whitespace-separated with quote support.

    Returns parsed rows if the data appears consistently delimited by
    single spaces (with optional quoting), or ``None`` if the data
    doesn't fit that pattern.

    Heuristic: if >80% of non-empty rows have the same field count
    when split on whitespace (respecting quotes), and that count is
    >= 3, we treat it as a single-space table.
    """
    parsed: list[list[str]] = []
    for line in lines:
        if not line.strip():
            continue
        fields = _split_whitespace_with_quotes(line.strip())
        if fields:
            parsed.append(fields)

    if len(parsed) < 2:
        return None

    counts = Counter(len(f) for f in parsed)
    if not counts:
        return None
    most_common_count, frequency = counts.most_common(1)[0]

    if most_common_count < 3:
        return None

    if frequency / len(parsed) < 0.8:
        return None

    return [f for f in parsed if len(f) == most_common_count]


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
    # If a data-row content-start hint is nearby, use the nearest one.
    # hints is sorted ascending (as produced by _find_content_starts), so
    # the closest hint must be the one just below or at/above pos. Use
    # bisect to find those two candidates in O(log H) instead of scanning
    # the full hint list per boundary.
    if hints:
        idx = bisect.bisect_left(hints, pos)
        candidates = []
        if idx > 0:
            candidates.append(hints[idx - 1])
        if idx < len(hints):
            candidates.append(hints[idx])

        best = None
        best_dist = 4
        for h in candidates:
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
        # Strategy 1: split on 2+ spaces (works for most CLI tools)
        boundaries = _find_column_boundaries(raw)
        ncols = len(_split(raw[0], boundaries))

        # Strategy 2: single-space with quote support
        # Used when the 2+ space split either:
        #   - produces 0-1 columns (no 2+ space gaps found)
        #   - produces far fewer columns than a consistent whitespace split
        #     (e.g. ``eza -l`` where right-aligned columns create unstable gaps)
        single_space_rows: list[list[str]] | None = None
        if ncols < 2:
            single_space_rows = _try_parse_single_space(raw)
        else:
            # Also try single-space — if it gives >= 2x the columns, the
            # 2+ space boundaries are likely cutting through fields.
            candidate = _try_parse_single_space(raw)
            if candidate is not None and len(candidate[0]) >= ncols * 2:
                single_space_rows = candidate

        if single_space_rows is not None:
            ncols = len(single_space_rows[0])
            header = [f"col{i+1}" for i in range(ncols)]
            return Table(header, single_space_rows)

        header = [f"col{i+1}" for i in range(ncols)]
        rows = [_split(line, boundaries) for line in raw]
        return Table(header, rows)

    header, rows, _trailing = _parse_table_lines(lines)
    return Table(header, rows)


def read_input(path: str | None) -> list[str]:
    """Read lines from file or stdin.

    Note: when reading from stdin, this calls ``sys.stdin.readlines()``,
    which blocks until the upstream producer closes its write end. If
    you pipe from an unbounded stream (e.g. ``tail -f``), wrap the call
    in a timeout — tabletop is intended for finite inputs.
    """
    if path:
        try:
            with open(path, encoding="utf-8") as f:
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
