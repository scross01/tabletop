"""Table output formatters: Rich, plain, CSV, TSV, JSON."""

from __future__ import annotations

import csv
import json
import sys

from rich.console import Console
from rich.table import Table as RichTable

from .parser import Table


def _pad_row(row: list[str], ncols: int) -> list[str]:
    """Pad/truncate a row to exactly ``ncols`` entries with empty strings."""
    return row + [""] * (ncols - len(row))


def rich(table: Table, console: Console) -> None:
    """Render a Rich table to the terminal."""
    rt = RichTable(
        show_header=True,
        header_style="bold cyan",
        show_lines=False,
        pad_edge=True,
        expand=False,
    )
    for col in table.header:
        rt.add_column(col)

    for row in table.rows:
        rt.add_row(*_pad_row(row, table.ncols))

    console.print(rt)


def plain(table: Table, file=None) -> None:
    """Output a plain space-aligned table."""
    if file is None:
        file = sys.stdout
    if not table.header:
        return

    widths = table.col_widths
    sep = "  "

    header_line = sep.join(h.ljust(widths[i]) for i, h in enumerate(table.header))
    print(header_line, file=file)

    for row in table.rows:
        padded = _pad_row(row, table.ncols)
        line = sep.join(padded[i].ljust(widths[i]) for i in range(table.ncols))
        print(line, file=file)


def csv_out(table: Table, file=None) -> None:
    """Output as CSV."""
    if file is None:
        file = sys.stdout
    w = csv.writer(file)
    w.writerow(table.header)
    for row in table.rows:
        w.writerow(_pad_row(row, table.ncols))


def tsv_out(table: Table, file=None) -> None:
    """Output as TSV."""
    if file is None:
        file = sys.stdout
    print("\t".join(table.header), file=file)
    for row in table.rows:
        print("\t".join(_pad_row(row, table.ncols)), file=file)


def json_out(table: Table, file=None) -> None:
    """Output as JSON array of objects."""
    if file is None:
        file = sys.stdout
    records = []
    for row in table.rows:
        records.append(dict(zip(table.header, _pad_row(row, table.ncols))))
    print(json.dumps(records, indent=2), file=file)


def markdown_out(table: Table, file=None) -> None:
    """Output as a Markdown table."""
    if file is None:
        file = sys.stdout
    if not table.header:
        return

    widths = table.col_widths
    sep = " | "

    header_line = sep.join(h.ljust(widths[i]) for i, h in enumerate(table.header))
    print(f"| {header_line} |", file=file)
    print("| " + sep.join("-" * w for w in widths) + " |", file=file)

    for row in table.rows:
        padded = _pad_row(row, table.ncols)
        line = sep.join(padded[i].ljust(widths[i]) for i in range(table.ncols))
        print(f"| {line} |", file=file)


def _dkvp_val(v: str) -> str:
    if "," in v:
        return '"' + v.replace('"', '\\"') + '"'
    return v


def dkvp_out(table: Table, file=None) -> None:
    """Output as DKVP (key=value pairs)."""
    if file is None:
        file = sys.stdout
    for row in table.rows:
        padded = _pad_row(row, table.ncols)
        pairs = [f"{table.header[i]}={_dkvp_val(padded[i])}" for i in range(table.ncols)]
        print(", ".join(pairs), file=file)
