"""Tests for tabletop parser."""

import tempfile
from pathlib import Path

import pytest

from tabletop.parser import parse, read_input, Table


SAMPLE = """\
NAME                             ID              SIZE      MODIFIED
lfm2.5:8b                       9cf756159fc2    5.2 GB    8 hours ago
smollm2:1.7b                    cef4a1e09247    1.8 GB    8 hours ago
smollm2:135m                    9077fe9d2ae1    270 MB    9 hours ago
gemma4:12b                       4eb23ef187e2    7.6 GB    30 hours ago
granite4.1:3b                    6fd349357287    2.1 GB    45 hours ago
"""


def test_parse_basic():
    t = parse(SAMPLE.splitlines())
    assert t.header == ["NAME", "ID", "SIZE", "MODIFIED"]
    assert len(t) == 5


def test_parse_preserves_single_spaces():
    """Fields with single spaces like '5.2 GB' should stay intact."""
    t = parse(SAMPLE.splitlines())
    sizes = [row[2] for row in t.rows]
    assert "5.2 GB" in sizes
    assert "270 MB" in sizes


def test_copy():
    t = parse(SAMPLE.splitlines())
    t2 = t.copy()
    t2.rows.pop()
    assert len(t) == 5  # original unchanged
    assert len(t2) == 4


def test_separator_line():
    """Separator line (---...---) between header and data should be skipped."""
    lines = [
        "NAME    SIZE    STATUS",
        "------  ------  ------",
        "alpha   100MB   done",
        "beta    200MB   running",
    ]
    t = parse(lines)
    assert t.header == ["NAME", "SIZE", "STATUS"]
    assert len(t) == 2
    assert t.rows[0][0] == "alpha"
    assert t.rows[1][0] == "beta"


def test_separator_eq():
    """=== separator should also be skipped."""
    lines = [
        "NAME    SIZE",
        "===     ===",
        "alpha   100MB",
    ]
    t = parse(lines)
    assert t.header == ["NAME", "SIZE"]
    assert len(t) == 1


def test_trailing_lines():
    """Trailing non-table lines with different column count are trimmed."""
    lines = [
        "NAME    SIZE    STATUS",
        "alpha   100MB   done",
        "beta    200MB   running",
        "",
        "Total: 300MB across 2 items",
    ]
    t = parse(lines)
    assert t.header == ["NAME", "SIZE", "STATUS"]
    assert len(t) == 2
    assert t.rows[0][0] == "alpha"


def test_separator_and_trailing():
    """Both separator and trailing lines."""
    lines = [
        "ID    SIZE    LAST_ACCESSED    MODIFIED",
        "----------------------------------------------  ------  -------------  ----",
        "repo/model-a   134.5M   5 days ago    2 weeks ago",
        "repo/model-b   91.8M    5 days ago    2 weeks ago",
        "",
        "Found 2 repo(s) for a total of 226.3M on disk.",
    ]
    t = parse(lines)
    assert t.header == ["ID", "SIZE", "LAST_ACCESSED", "MODIFIED"]
    assert len(t) == 2
    assert t.rows[0][0] == "repo/model-a"
    assert t.rows[1][0] == "repo/model-b"


def test_no_header():
    lines = ["alpha  100  x", "beta   200  y"]
    t = parse(lines, has_header=False)
    assert t.header == ["col1", "col2", "col3"]
    assert len(t) == 2
    assert t.rows[0] == ["alpha", "100", "x"]


def test_parse_empty():
    t = parse([])
    assert not t
    assert t.header == []


def test_parse_whitespace_only():
    t = parse(["  ", "   ", ""])
    assert not t


def test_column_index_by_name():
    t = parse(SAMPLE.splitlines())
    assert t.column_index("NAME") == 0
    assert t.column_index("name") == 0  # case-insensitive
    assert t.column_index("SIZE") == 2
    assert t.column_index("nonexistent") is None


def test_column_index_by_number():
    t = parse(SAMPLE.splitlines())
    assert t.column_index("1") == 0
    assert t.column_index("3") == 2
    assert t.column_index("4") == 3
    assert t.column_index("0") is None  # 1-based
    assert t.column_index("5") is None  # out of range


def test_ncols():
    t = parse(SAMPLE.splitlines())
    assert t.ncols == 4


def test_col_widths():
    t = parse(SAMPLE.splitlines())
    widths = t.col_widths
    assert widths[0] == len("granite4.1:3b")  # longest NAME in test SAMPLE
    assert widths[2] == len("5.2 GB")  # longest SIZE


def test_split_whitespace_with_quotes():
    from tabletop.parser import _split_whitespace_with_quotes

    # Basic split
    assert _split_whitespace_with_quotes("a b c") == ["a", "b", "c"]

    # Double-quoted value with spaces
    assert _split_whitespace_with_quotes('a "b c" d') == ["a", "b c", "d"]

    # Single-quoted value with spaces
    assert _split_whitespace_with_quotes("a 'b c' d") == ["a", "b c", "d"]

    # Mixed quotes
    assert _split_whitespace_with_quotes('a "b c" d "e f"') == ["a", "b c", "d", "e f"]

    # Unmatched quote — treated as literal
    assert _split_whitespace_with_quotes('a "b c') == ["a", "b c"]

    # No quotes, just whitespace
    assert _split_whitespace_with_quotes("  a   b   c  ") == ["a", "b", "c"]

    # Empty / whitespace only
    assert _split_whitespace_with_quotes("") == []
    assert _split_whitespace_with_quotes("   ") == []

    # Single value
    assert _split_whitespace_with_quotes("hello") == ["hello"]


def test_try_parse_single_space_basic():
    from tabletop.parser import _try_parse_single_space

    lines = ["a b c", "d e f", "g h i"]
    result = _try_parse_single_space(lines)
    assert result == [["a", "b", "c"], ["d", "e", "f"], ["g", "h", "i"]]


def test_try_parse_single_space_with_quotes():
    from tabletop.parser import _try_parse_single_space

    lines = ["a 'b c' d", "e 'f g' h", "i 'j k' l"]
    result = _try_parse_single_space(lines)
    assert result is not None
    assert result[0] == ["a", "b c", "d"]
    assert result[1] == ["e", "f g", "h"]
    assert result[2] == ["i", "j k", "l"]


def test_try_parse_single_space_inconsistent():
    """Inconsistent column counts should return None."""
    from tabletop.parser import _try_parse_single_space

    lines = ["a b c", "d e", "f g h i"]
    result = _try_parse_single_space(lines)
    assert result is None


def test_try_parse_single_space_fewer_than_3_cols():
    """Tables with < 3 columns should return None (not worth treating as table)."""
    from tabletop.parser import _try_parse_single_space

    lines = ["a b", "c d"]
    result = _try_parse_single_space(lines)
    assert result is None


def test_parse_no_header_single_space():
    """No-header input with single-space columns should fall back."""
    lines = ["name age status", "foo 12 active", "bar 34 inactive"]
    t = parse(lines, has_header=False)
    assert t.header == ["col1", "col2", "col3"]
    assert len(t) == 3
    assert t.rows[0] == ["name", "age", "status"]
    assert t.rows[2] == ["bar", "34", "inactive"]


def test_parse_no_header_with_quotes():
    """No-header input with quoted values should be handled."""
    lines = ["alpha 'hello world' 42", "beta 'foo bar' 99"]
    t = parse(lines, has_header=False)
    assert len(t) == 2
    assert t.ncols == 3
    assert t.rows[0][1] == "hello world"
    assert t.rows[1][1] == "foo bar"


def test_snap_to_space_wide_table():
    """Wide columns should still snap correctly."""
    lines = [
        "COMMAND  VERY_LONG_COLUMN_NAME_12345678901234567890  STATUS",
        "foo      some_value_here_that_is_quite_long         ok",
    ]
    t = parse(lines)
    assert len(t) == 1
    assert t.rows[0][0] == "foo"
    assert t.rows[0][1] == "some_value_here_that_is_quite_long"
    assert t.rows[0][2] == "ok"


class TestReadInput:
    def test_read_file(self):
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
            f.write("test\n")
            path = f.name
        try:
            lines = read_input(path)
            assert lines == ["test\n"]
        finally:
            Path(path).unlink()

    def test_read_missing_file(self):
        with pytest.raises(SystemExit):
            read_input("/nonexistent/path/file.txt")

    def test_read_directory(self):
        with pytest.raises(SystemExit):
            read_input("/tmp")


# ── Unicode outline table tests ───────────────────────────────


class TestOutlineDetection:
    def test_detect_outline_table_basic(self):
        """A basic outline table with ┏ top border and │ rows should be detected."""
        from tabletop.parser import _detect_outline_table

        lines = [
            "┏━━━━━━┳━━━━━━┓",
            "┃ Name ┃ Size ┃",
            "┡━━━━━━╇━━━━━━┩",
            "│ foo  │ 100  │",
            "│ bar  │ 200  │",
            "└──────┴──────┘",
        ]
        assert _detect_outline_table(lines) is True

    def test_detect_outline_table_with_title(self):
        """Title before the outline table should not prevent detection."""
        from tabletop.parser import _detect_outline_table

        lines = [
            "                                    Installed Skills                                     ",
            "┏━━━━━━┳━━━━━━┓",
            "┃ Name ┃ Size ┃",
            "┡━━━━━━╇━━━━━━┩",
            "│ foo  │ 100  │",
            "└──────┴──────┘",
        ]
        assert _detect_outline_table(lines) is True

    def test_detect_not_outline_table(self):
        """Regular space-aligned tables should not be detected as outline."""
        from tabletop.parser import _detect_outline_table

        lines = [
            "NAME    SIZE    STATUS",
            "------  ------  ------",
            "alpha   100MB   done",
        ]
        assert _detect_outline_table(lines) is False

    def test_detect_outline_empty(self):
        from tabletop.parser import _detect_outline_table

        assert _detect_outline_table([]) is False
        assert _detect_outline_table([""]) is False


class TestOutlineParsing:
    def test_parse_outline_basic(self):
        """Parse a simple outline table with header and data rows."""
        lines = [
            "┏━━━━━━━━┳━━━━━━━━┳━━━━━━━━┓",
            "┃ Name   ┃ Size   ┃ Status ┃",
            "┡━━━━━━━━╇━━━━━━━━╇━━━━━━━━┩",
            "│ alpha  │ 100MB  │ done   │",
            "│ beta   │ 200MB  │ active │",
            "└────────┴────────┴────────┘",
        ]
        t = parse(lines)
        assert t.header == ["Name", "Size", "Status"]
        assert len(t) == 2
        assert t.rows[0] == ["alpha", "100MB", "done"]
        assert t.rows[1] == ["beta", "200MB", "active"]

    def test_parse_outline_with_title_and_footer(self):
        """Title before and summary after should be ignored."""
        lines = [
            "                          My Table                          ",
            "┏━━━━━━┳━━━━━━┓",
            "┃ A    ┃ B    ┃",
            "┡━━━━━━╇━━━━━━┩",
            "│ 1    │ 2    │",
            "│ 3    │ 4    │",
            "└──────┴──────┘",
            "Total: 10 items",
        ]
        t = parse(lines)
        assert t.header == ["A", "B"]
        assert len(t) == 2
        assert t.rows[0] == ["1", "2"]
        assert t.rows[1] == ["3", "4"]

    def test_parse_outline_empty_fields(self):
        """Empty fields in outline rows should be preserved."""
        lines = [
            "┏━━━━━━━━┳━━━━━━━━┳━━━━━━━━┓",
            "┃ Name   ┃ Cat    ┃ Status ┃",
            "┡━━━━━━━━╇━━━━━━━━╇━━━━━━━━┩",
            "│ foo    │        │ on     │",
            "│ bar    │ test   │        │",
            "└────────┴────────┴────────┘",
        ]
        t = parse(lines)
        assert t.rows[0] == ["foo", "", "on"]
        assert t.rows[1] == ["bar", "test", ""]

    def test_parse_outline_no_header_separator(self):
        """Outline table without ┡ separator: first │ row becomes header."""
        lines = [
            "┏━━━━━━┳━━━━━━┓",
            "│ Name │ Size │",
            "│ foo  │ 100  │",
            "│ bar  │ 200  │",
            "└──────┴──────┘",
        ]
        t = parse(lines)
        assert t.header == ["Name", "Size"]
        assert len(t) == 2

    def test_parse_outline_preserves_spaces_in_values(self):
        """Values with internal spaces should be preserved."""
        lines = [
            "┏━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━┓",
            "┃ Name                ┃ Type   ┃",
            "┡━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━┩",
            "│ hello world         │ test   │",
            "│ foo bar baz         │ other  │",
            "└────────────────────┴────────┘",
        ]
        t = parse(lines)
        assert t.rows[0][0] == "hello world"
        assert t.rows[1][0] == "foo bar baz"

    def test_parse_outline_mid_separator(self):
        """Outline table with ├─┼─┤ mid-table separator."""
        lines = [
            "┏━━━━━━┳━━━━━━┓",
            "┃ A    ┃ B    ┃",
            "┡━━━━━━╇━━━━━━┩",
            "│ 1    │ 2    │",
            "├──────┼──────┤",
            "│ 3    │ 4    │",
            "└──────┴──────┘",
        ]
        t = parse(lines)
        assert len(t) == 2
        assert t.rows[0] == ["1", "2"]
        assert t.rows[1] == ["3", "4"]
