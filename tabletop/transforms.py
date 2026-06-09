"""Table transforms: sort, filter, column selection/removal."""

from __future__ import annotations

import re
from typing import Any

from .parser import Table


class TabletopError(Exception):
    """Raised on invalid input or table operations."""





# ── time period parsing ─────────────────────────────────────────────

TIME_UNITS = {
    "second": 1,
    "seconds": 1,
    "sec": 1,
    "secs": 1,
    "minute": 60,
    "minutes": 60,
    "min": 60,
    "mins": 60,
    "hour": 3600,
    "hours": 3600,
    "hr": 3600,
    "hrs": 3600,
    "day": 86400,
    "days": 86400,
    "week": 604800,
    "weeks": 604800,
    "month": 2592000,  # 30 days
    "months": 2592000,
    "year": 31536000,  # 365 days
    "years": 31536000,
}

_TIME_RE = re.compile(
    r"^\s*(\d+(?:\.\d+)?)\s+(second|seconds|sec|secs|minute|minutes|min|mins|"
    r"hour|hours|hr|hrs|day|days|week|weeks|month|months|year|years)s?\s*(?:ago)?\s*$",
    re.IGNORECASE,
)


def _parse_time(val: str) -> float | None:
    """Parse a human-readable time string into seconds.

    Returns None if the value doesn't look like a time period.
    Examples: "8 hours ago" → 28800, "30 hours ago" → 108000
    """
    m = _TIME_RE.match(val.strip())
    if not m:
        return None
    num = float(m.group(1))
    unit = m.group(2).lower()
    return num * TIME_UNITS.get(unit, 0)


# ── size parsing ────────────────────────────────────────────────────

UNIT_MULTIPLIERS = {
    "b": 1,
    "byte": 1,
    "bytes": 1,
    "k": 1024,
    "m": 1024**2,
    "g": 1024**3,
    "t": 1024**4,
    "p": 1024**5,
    "e": 1024**6,
}

# Match: optional number, optional whitespace, optional unit
_SIZE_RE = re.compile(
    r"^\s*([0-9]*\.?[0-9]+)\s*([a-zA-Z]+)?\s*$"
)


def _parse_size(val: str) -> float | None:
    """Parse a human-readable size string into bytes.

    Returns None if the value doesn't look like a size.
    Examples: "5.2 GB" → 5.6038...e9, "270 MB" → 2.831...e8, "208Ki" → 212992
    """
    m = _SIZE_RE.match(val.strip())
    if not m:
        return None
    num = float(m.group(1))
    unit = (m.group(2) or "").lower()
    # Normalize: "kib" → "k", "kb" → "k", "ki" → "k", "mib" → "m", "mb" → "m"
    if unit.endswith("ib"):
        unit = unit[:-2]
    elif unit.endswith("b") and len(unit) > 1:
        unit = unit[:-1]
    elif unit.endswith("i") and len(unit) > 1:
        unit = unit[:-1]
    if unit in UNIT_MULTIPLIERS:
        return num * UNIT_MULTIPLIERS[unit]
    # Bare number with no recognized unit — still treat as numeric
    if not unit:
        return num
    return None


def _detect_column_type(values: list[str]) -> str:
    """Detect whether a column is 'size', 'time', 'numeric', or 'text'.

    'size':    majority of non-empty values parse as sizes with units
    'time':    majority parse as time periods ("8 hours ago")
    'numeric': majority parse as bare numbers
    'text':    everything else
    """
    non_empty = [v for v in values if v.strip()]
    if not non_empty:
        return "text"

    size_count = 0
    time_count = 0
    num_count = 0
    for v in non_empty:
        if _parse_time(v) is not None:
            time_count += 1
            continue
        parsed = _parse_size(v)
        if parsed is not None:
            # Check if it actually had a unit (size) or was bare (numeric)
            m = _SIZE_RE.match(v.strip())
            if m and m.group(2):
                size_count += 1
            else:
                num_count += 1
        elif re.match(r"^[\d.,\-]+%?\s*$", v.strip()):
            num_count += 1

    total = len(non_empty)
    if time_count / total > 0.5:
        return "time"
    if size_count / total > 0.5:
        return "size"
    if (size_count + num_count) / total > 0.5:
        return "numeric"
    return "text"


def _sort_key_for_type(col_type: str, val: str) -> tuple[int, Any]:
    """Return a sort key appropriate for the column type."""
    if col_type == "time":
        parsed = _parse_time(val)
        if parsed is not None:
            return (0, parsed)
        return (1, val.lower())

    if col_type == "size":
        parsed = _parse_size(val)
        if parsed is not None:
            return (0, parsed)
        return (1, val.lower())

    if col_type == "numeric":
        try:
            return (0, float(re.sub(r"[^0-9.\-]", "", val)))
        except (ValueError, TypeError):
            return (1, val.lower())

    # text
    return (0, val.lower())


# ── transforms ──────────────────────────────────────────────────────

def sort_by(table: Table, col_spec: str, reverse: bool = False) -> Table:
    """Sort rows by column values with type-aware ordering (numeric, size, time, text)."""
    idx = table.column_index(col_spec)
    if idx is None:
        raise TabletopError(f"unknown column: {col_spec}")

    col_values = [row[idx] if idx < len(row) else "" for row in table.rows]
    col_type = _detect_column_type(col_values)

    t = table.copy()
    t.rows = sorted(
        t.rows,
        key=lambda row: _sort_key_for_type(col_type, row[idx] if idx < len(row) else ""),
        reverse=reverse,
    )
    return t


def filter_by(table: Table, col_spec: str, pattern: str) -> Table:
    """Keep only rows where column matches a regex pattern (case-insensitive)."""
    idx = table.column_index(col_spec)
    if idx is None:
        raise TabletopError(f"unknown column: {col_spec}")

    try:
        compiled = re.compile(pattern, re.IGNORECASE)
    except re.error as e:
        raise TabletopError(f"invalid regex: {e}")

    t = table.copy()
    t.rows = [
        row for row in t.rows
        if idx < len(row) and compiled.search(row[idx])
    ]
    return t


def select_columns(table: Table, col_specs: list[str]) -> Table:
    """Return a new table with only the named columns preserved."""
    indices = []
    new_header = []
    for spec in col_specs:
        idx = table.column_index(spec)
        if idx is None:
            raise TabletopError(f"unknown column: {spec}")
        indices.append(idx)
        new_header.append(table.header[idx])

    new_rows = [
        [row[i] if i < len(row) else "" for i in indices]
        for row in table.rows
    ]
    return Table(new_header, new_rows)


def remove_columns(table: Table, col_specs: list[str]) -> Table:
    """Return a new table with specified columns removed."""
    remove = set()
    for spec in col_specs:
        idx = table.column_index(spec)
        if idx is None:
            raise TabletopError(f"unknown column: {spec}")
        remove.add(idx)

    keep = [i for i in range(table.ncols) if i not in remove]
    new_header = [table.header[i] for i in keep]
    new_rows = [
        [row[i] if i < len(row) else "" for i in keep]
        for row in table.rows
    ]
    return Table(new_header, new_rows)


def head(table: Table, n: int) -> Table:
    """Return a new table containing only the first N rows."""
    t = table.copy()
    t.rows = t.rows[:n]
    return t


def tail(table: Table, n: int) -> Table:
    """Return a new table containing only the last N rows."""
    t = table.copy()
    t.rows = t.rows[-n:]
    return t


def unique(table: Table, col_spec: str | None = None) -> Table:
    """Remove duplicate rows, optionally keying on a single column."""
    if col_spec:
        idx = table.column_index(col_spec)
        if idx is None:
            raise TabletopError(f"unknown column: {col_spec}")
        seen = set()
        t = table.copy()
        t.rows = []
        for row in table.rows:
            key = row[idx] if idx < len(row) else ""
            if key not in seen:
                seen.add(key)
                t.rows.append(row)
        return t
    else:
        t = table.copy()
        seen = set()
        t.rows = []
        for row in table.rows:
            frozen = tuple(row)
            if frozen not in seen:
                seen.add(frozen)
                t.rows.append(row)
        return t


def stats(table: Table) -> Table:
    """Return a summary table with column-level statistics (count, unique, samples)."""
    rows = []
    for i, col in enumerate(table.header):
        values = [row[i] if i < len(row) else "" for row in table.rows]
        non_empty = [v for v in values if v.strip()]
        unique_vals = set(non_empty)
        sample = non_empty[:3] if non_empty else ["(empty)"]
        rows.append([
            col,
            str(len(values)),
            str(len(unique_vals)),
            ", ".join(sample),
        ])
    return Table(["COLUMN", "ROWS", "UNIQUE", "SAMPLES"], rows)
