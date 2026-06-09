"""Tests for tabletop output formatters."""

import io
from tabletop.parser import parse
from tabletop.output import plain, csv_out, tsv_out, json_out, markdown_out, dkvp_out


SAMPLE = """\
NAME    SIZE    MODIFIED
alpha   100 MB  1 day ago
beta    2.5 GB  2 days ago
gamma   50 MB   3 days ago
"""


def _get_table():
    return parse(SAMPLE.splitlines())


def test_plain_output():
    t = _get_table()
    buf = io.StringIO()
    plain(t, file=buf)
    out = buf.getvalue()
    lines = out.strip().split("\n")
    assert "NAME" in lines[0]
    assert "alpha" in lines[1]
    assert "100 MB" in lines[1]


def test_plain_alignment():
    t = _get_table()
    buf = io.StringIO()
    plain(t, file=buf)
    out = buf.getvalue()
    lines = out.strip().split("\n")
    # All lines should be same length (padded)
    lengths = [len(l) for l in lines]
    assert len(set(lengths)) == 1


def test_csv_output():
    t = _get_table()
    buf = io.StringIO()
    csv_out(t, file=buf)
    out = buf.getvalue()
    lines = out.strip().split("\n")
    assert lines[0].rstrip("\r") == "NAME,SIZE,MODIFIED"
    assert "alpha,100 MB,1 day ago" in lines[1]


def test_tsv_output():
    t = _get_table()
    buf = io.StringIO()
    tsv_out(t, file=buf)
    out = buf.getvalue()
    lines = out.strip().split("\n")
    assert lines[0] == "NAME\tSIZE\tMODIFIED"
    assert "alpha\t100 MB\t1 day ago" in lines[1]


def test_json_output():
    t = _get_table()
    buf = io.StringIO()
    json_out(t, file=buf)
    import json
    data = json.loads(buf.getvalue())
    assert len(data) == 3
    assert data[0]["NAME"] == "alpha"
    assert data[0]["SIZE"] == "100 MB"


def test_markdown_output():
    t = _get_table()
    buf = io.StringIO()
    markdown_out(t, file=buf)
    out = buf.getvalue()
    lines = out.strip().split("\n")
    assert lines[0].startswith("| NAME")
    assert "---" in lines[1]
    assert "| alpha" in lines[2]


def test_dkvp_output():
    t = _get_table()
    buf = io.StringIO()
    dkvp_out(t, file=buf)
    out = buf.getvalue()
    lines = out.strip().split("\n")
    assert "NAME=alpha" in lines[0]
    assert "SIZE=100 MB" in lines[0]


def test_dkvp_quotes_commas():
    t = parse("A    B\n1,2  3".splitlines())
    buf = io.StringIO()
    dkvp_out(t, file=buf)
    assert 'A="1,2"' in buf.getvalue()
