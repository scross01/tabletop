"""Tests for tabletop transforms."""

import pytest
from tabletop.parser import parse
from tabletop.transforms import (
    sort_by,
    filter_by,
    select_columns,
    remove_columns,
    head,
    tail,
    unique,
    stats,
    _parse_size,
    _parse_time,
    _detect_column_type,
    TabletopError,
)


SAMPLE = """\
NAME                             ID              SIZE      MODIFIED
lfm2.5:8b                       9cf756159fc2    5.2 GB    8 hours ago
smollm2:1.7b                    cef4a1e09247    1.8 GB    8 hours ago
smollm2:135m                    9077fe9d2ae1    270 MB    9 hours ago
gemma4:12b                       4eb23ef187e2    7.6 GB    30 hours ago
granite4.1:3b                    6fd349357287    2.1 GB    45 hours ago
"""


# ── size parsing ────────────────────────────────────────────────────

class TestParseSize:
    def test_bytes(self):
        assert _parse_size("100") == 100.0

    def test_kb(self):
        assert _parse_size("1 KB") == 1024
        assert _parse_size("1kB") == 1024
        assert _parse_size("1KiB") == 1024  # strips trailing 'i'

    def test_mb(self):
        assert _parse_size("270 MB") == 270 * 1024**2

    def test_gb(self):
        assert _parse_size("5.2 GB") == pytest.approx(5.2 * 1024**3)

    def test_tb(self):
        assert _parse_size("1 TB") == 1024**4

    def test_pb(self):
        assert _parse_size("1 PB") == 1024**5

    def test_float(self):
        assert _parse_size("1.5 MB") == pytest.approx(1.5 * 1024**2)

    def test_no_space(self):
        assert _parse_size("5.2GB") == pytest.approx(5.2 * 1024**3)

    def test_unknown_unit(self):
        assert _parse_size("100 xyz") is None

    def test_empty(self):
        assert _parse_size("") is None

    def test_text(self):
        assert _parse_size("hello world") is None


# ── time parsing ────────────────────────────────────────────────────

class TestParseTime:
    def test_seconds(self):
        assert _parse_time("30 seconds ago") == 30

    def test_minutes(self):
        assert _parse_time("5 minutes ago") == 300

    def test_hours(self):
        assert _parse_time("8 hours ago") == 28800

    def test_days(self):
        assert _parse_time("12 days ago") == 12 * 86400

    def test_weeks(self):
        assert _parse_time("2 weeks ago") == 2 * 604800

    def test_months(self):
        assert _parse_time("7 months ago") == 7 * 2592000

    def test_years(self):
        assert _parse_time("1 year ago") == 31536000

    def test_abbreviations(self):
        assert _parse_time("30 secs ago") == 30
        assert _parse_time("5 mins ago") == 300
        assert _parse_time("8 hrs ago") == 28800

    def test_decimal(self):
        assert _parse_time("1.5 hours ago") == 5400

    def test_case_insensitive(self):
        assert _parse_time("8 HOURS ago") == 28800

    def test_not_time(self):
        assert _parse_time("hello world") is None
        assert _parse_time("5.2 GB") is None
        assert _parse_time("100") is None

    def test_without_ago(self):
        assert _parse_time("8 hours") == 28800
        assert _parse_time("3 weeks") == 3 * 604800
        assert _parse_time("1 month") == 2592000

    def test_double_plural_rejected(self):
        assert _parse_time("8 hourss ago") is None
        assert _parse_time("3 dayss") is None
        assert _parse_time("1 minutess ago") is None


# ── column type detection ───────────────────────────────────────────

class TestDetectColumnType:
    def test_size_column(self):
        assert _detect_column_type(["5.2 GB", "1.8 GB", "270 MB"]) == "size"

    def test_numeric_column(self):
        assert _detect_column_type(["100", "200", "300"]) == "numeric"

    def test_text_column(self):
        assert _detect_column_type(["hello", "world", "foo"]) == "text"

    def test_mixed_name_column(self):
        """Names with numbers should still be text."""
        assert _detect_column_type(["gemma4:12b", "smollm2:1.7b"]) == "text"

    def test_empty(self):
        assert _detect_column_type([]) == "text"

    def test_mostly_sizes(self):
        """Majority size values → detect as size."""
        vals = ["5.2 GB", "1.8 GB", "270 MB", "x"]
        assert _detect_column_type(vals) == "size"

    def test_mostly_numeric(self):
        """Majority numeric values → detect as numeric."""
        vals = ["100", "200", "abc"]
        assert _detect_column_type(vals) == "numeric"

    def test_time_column(self):
        assert _detect_column_type(["8 hours ago", "30 hours ago", "12 days ago"]) == "time"

    def test_commas_in_numbers(self):
        assert _detect_column_type(["1,234", "567", "89"]) == "numeric"


# ── sort ────────────────────────────────────────────────────────────

class TestSortBy:
    def test_sort_alpha_ascending(self):
        t = parse(SAMPLE.splitlines())
        t2 = sort_by(t, "NAME")
        names = [r[0] for r in t2.rows]
        assert names == sorted(names)

    def test_sort_alpha_descending(self):
        t = parse(SAMPLE.splitlines())
        t2 = sort_by(t, "NAME", reverse=True)
        names = [r[0] for r in t2.rows]
        assert names == sorted(names, reverse=True)

    def test_sort_size_ascending(self):
        t = parse(SAMPLE.splitlines())
        t2 = sort_by(t, "SIZE")
        sizes = [r[2] for r in t2.rows]
        # 270 MB < 1.8 GB < 2.1 GB < 5.2 GB < 7.6 GB
        assert sizes == ["270 MB", "1.8 GB", "2.1 GB", "5.2 GB", "7.6 GB"]

    def test_sort_size_descending(self):
        t = parse(SAMPLE.splitlines())
        t2 = sort_by(t, "SIZE", reverse=True)
        sizes = [r[2] for r in t2.rows]
        assert sizes == ["7.6 GB", "5.2 GB", "2.1 GB", "1.8 GB", "270 MB"]

    def test_sort_by_index(self):
        t = parse(SAMPLE.splitlines())
        t2 = sort_by(t, "3")  # SIZE column
        sizes = [r[2] for r in t2.rows]
        assert sizes == ["270 MB", "1.8 GB", "2.1 GB", "5.2 GB", "7.6 GB"]

    def test_sort_unknown_column(self):
        t = parse(SAMPLE.splitlines())
        with pytest.raises(TabletopError):
            sort_by(t, "nonexistent")

    def test_sort_time_ascending(self):
        lines = [
            "NAME  MODIFIED",
            "a     12 days ago",
            "b     8 hours ago",
            "c     7 months ago",
            "d     30 hours ago",
        ]
        t = parse(lines)
        t2 = sort_by(t, "MODIFIED")
        mods = [r[1] for r in t2.rows]
        # 8 hours < 30 hours < 12 days < 7 months
        assert mods == ["8 hours ago", "30 hours ago", "12 days ago", "7 months ago"]

    def test_sort_time_descending(self):
        lines = [
            "NAME  MODIFIED",
            "a     8 hours ago",
            "b     7 months ago",
            "c     12 days ago",
        ]
        t = parse(lines)
        t2 = sort_by(t, "MODIFIED", reverse=True)
        mods = [r[1] for r in t2.rows]
        assert mods == ["7 months ago", "12 days ago", "8 hours ago"]

    def test_sort_commas_in_numbers(self):
        lines = [
            "NAME  VALUE",
            "a     1,234",
            "b     567",
            "c     89",
        ]
        t = parse(lines)
        t2 = sort_by(t, "VALUE")
        vals = [r[1] for r in t2.rows]
        assert vals == ["89", "567", "1,234"]


# ── filter ──────────────────────────────────────────────────────────

class TestFilterBy:
    def test_filter_exact(self):
        t = parse(SAMPLE.splitlines())
        t2 = filter_by(t, "NAME", "gemma4:12b")
        assert len(t2) == 1
        assert t2.rows[0][0] == "gemma4:12b"

    def test_filter_regex(self):
        t = parse(SAMPLE.splitlines())
        t2 = filter_by(t, "NAME", "gemma")
        assert len(t2) == 1

    def test_filter_case_insensitive(self):
        t = parse(SAMPLE.splitlines())
        t2 = filter_by(t, "NAME", "GEMMA")
        assert len(t2) == 1

    def test_filter_no_match(self):
        t = parse(SAMPLE.splitlines())
        t2 = filter_by(t, "NAME", "nonexistent")
        assert len(t2) == 0

    def test_filter_alternation(self):
        t = parse(SAMPLE.splitlines())
        t2 = filter_by(t, "NAME", "gemma|granite")
        assert len(t2) == 2

    def test_filter_by_size(self):
        t = parse(SAMPLE.splitlines())
        t2 = filter_by(t, "SIZE", "GB")
        assert len(t2) == 4  # all except 270 MB

    def test_filter_invalid_regex(self):
        t = parse(SAMPLE.splitlines())
        with pytest.raises(TabletopError):
            filter_by(t, "NAME", "[invalid")

    def test_filter_redos_nested_quantifiers(self):
        t = parse(SAMPLE.splitlines())
        with pytest.raises(TabletopError, match="nested quantifiers"):
            filter_by(t, "NAME", "(a+)+")

    def test_filter_redos_star_group(self):
        t = parse(SAMPLE.splitlines())
        with pytest.raises(TabletopError, match="nested quantifiers"):
            filter_by(t, "NAME", "(.*)+b")

    def test_filter_redos_too_long(self):
        t = parse(SAMPLE.splitlines())
        with pytest.raises(TabletopError, match="too long"):
            filter_by(t, "NAME", "a" * 300)


# ── columns ─────────────────────────────────────────────────────────

class TestSelectColumns:
    def test_select_by_name(self):
        t = parse(SAMPLE.splitlines())
        t2 = select_columns(t, ["NAME", "SIZE"])
        assert t2.header == ["NAME", "SIZE"]
        assert t2.ncols == 2

    def test_select_by_index(self):
        t = parse(SAMPLE.splitlines())
        t2 = select_columns(t, ["1", "3"])
        assert t2.header == ["NAME", "SIZE"]

    def test_select_unknown(self):
        t = parse(SAMPLE.splitlines())
        with pytest.raises(TabletopError):
            select_columns(t, ["nonexistent"])


class TestRemoveColumns:
    def test_remove_by_name(self):
        t = parse(SAMPLE.splitlines())
        t2 = remove_columns(t, ["ID", "MODIFIED"])
        assert t2.header == ["NAME", "SIZE"]
        assert t2.ncols == 2

    def test_remove_by_index(self):
        t = parse(SAMPLE.splitlines())
        t2 = remove_columns(t, ["2", "4"])
        assert t2.header == ["NAME", "SIZE"]


# ── head/tail ───────────────────────────────────────────────────────

class TestHeadTail:
    def test_head(self):
        t = parse(SAMPLE.splitlines())
        t2 = head(t, 2)
        assert len(t2) == 2

    def test_head_0(self):
        t = parse(SAMPLE.splitlines())
        t2 = head(t, 0)
        assert len(t2) == 0

    def test_head_more_than_available(self):
        t = parse(SAMPLE.splitlines())
        t2 = head(t, 100)
        assert len(t2) == 5

    def test_tail(self):
        t = parse(SAMPLE.splitlines())
        t2 = tail(t, 2)
        assert len(t2) == 2
        assert t2.rows[0][0] == "gemma4:12b"
        assert t2.rows[1][0] == "granite4.1:3b"


# ── unique ──────────────────────────────────────────────────────────

class TestUnique:
    def test_unique_no_duplicates(self):
        t = parse(SAMPLE.splitlines())
        t2 = unique(t)
        assert len(t2) == 5  # all unique

    def test_unique_with_duplicates(self):
        lines = [
            "A  1",
            "B  2",
            "A  1",
            "C  3",
            "B  2",
        ]
        t = parse(lines, has_header=False)
        t2 = unique(t)
        assert len(t2) == 3

    def test_unique_by_column(self):
        lines = [
            "NAME  SIZE",
            "a     100",
            "b     200",
            "a     300",
        ]
        t = parse(lines)
        t2 = unique(t, "NAME")
        assert len(t2) == 2  # first 'a' kept
        assert t2.rows[0][1] == "100"


# ── stats ───────────────────────────────────────────────────────────

class TestStats:
    def test_stats(self):
        t = parse(SAMPLE.splitlines())
        t2 = stats(t)
        assert t2.header == ["COLUMN", "ROWS", "UNIQUE", "SAMPLES"]
        assert len(t2) == 4  # 4 columns
        # NAME column: 5 rows, 5 unique
        name_row = t2.rows[0]
        assert name_row[0] == "NAME"
        assert name_row[1] == "5"
        assert name_row[2] == "5"
