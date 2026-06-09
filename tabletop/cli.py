"""CLI entry point."""

from __future__ import annotations

import argparse
import sys

from rich.console import Console

from . import output as fmt
from .parser import Table, parse, read_input
from . import transforms as tf
from .transforms import TabletopError


VERSION = "0.1.0"


def _positive_int(val: str) -> int:
    try:
        n = int(val)
    except ValueError:
        raise argparse.ArgumentTypeError(f"must be a positive integer, got '{val}'")
    if n <= 0:
        raise argparse.ArgumentTypeError(f"must be a positive integer, got {n}")
    return n


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="tabletop",
        description="Reformat, sort, filter, and reshape space-aligned CLI tables.",
        epilog="""\
examples:
  ollama list | tabletop
  ollama list | tabletop -s 3
  ollama list | tabletop -sr name
  ollama list | tabletop -f name:gemma
  ollama list | tabletop -c name,size,modified
  ollama list | tabletop -r id
  ollama list | tabletop -s 3 -f name:gemma -c name,size
  ollama list | tabletop --csv
  ollama list | tabletop --json
  ollama list | tabletop --markdown
  ollama list | tabletop --stats
  ollama list | tabletop -H 5
  ollama list | tabletop -T 3
  ollama list | tabletop -u name
  docker ps | tabletop -c 1,2,3
  df -h | tabletop -c 1,2,3,5
""",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument(
        "--version", action="version", version=f"tabletop {VERSION}"
    )

    # Input
    p.add_argument(
        "file", nargs="?", default=None, metavar="FILE",
        help="Input file (default: stdin)",
    )

    # Output formats
    out = p.add_argument_group("output formats")
    out.add_argument(
        "--plain", action="store_true",
        help="space-aligned table (default when piped)",
    )
    out.add_argument(
        "--rich", action="store_true", dest="use_rich",
        help="Rich formatted table (default in terminal)",
    )
    out.add_argument("--csv", action="store_true", help="CSV output")
    out.add_argument("--tsv", action="store_true", help="TSV output")
    out.add_argument("--json", action="store_true", help="JSON array of objects")
    out.add_argument("--markdown", "--md", action="store_true", help="Markdown table")
    out.add_argument("--dkvp", action="store_true", help="DKVP (key=value) output")

    # Transforms
    tx = p.add_argument_group("transforms")
    tx.add_argument(
        "-s", "--sort", metavar="COL",
        help="Sort ascending by column (name or 1-based index)",
    )
    tx.add_argument(
        "-sr", "--sort-reverse", metavar="COL",
        help="Sort descending by column",
    )
    tx.add_argument(
        "-f", "--filter", metavar="COL:PAT", action="append", default=[],
        help="Keep rows where column matches regex (repeatable)",
    )
    tx.add_argument(
        "-c", "--columns", metavar="COLS",
        help="Show only these columns (comma-separated names or indices)",
    )
    tx.add_argument(
        "-r", "--remove", metavar="COLS",
        help="Remove these columns (comma-separated names or indices)",
    )
    tx.add_argument(
        "-H", "--head", metavar="N", type=_positive_int,
        help="Keep only first N rows",
    )
    tx.add_argument(
        "-T", "--tail", metavar="N", type=_positive_int,
        help="Keep only last N rows",
    )
    tx.add_argument(
        "-u", "--unique", metavar="COL", nargs="?", const="",
        help="Deduplicate rows (optionally by column)",
    )

    # Table options
    tbl = p.add_argument_group("table options")
    tbl.add_argument(
        "--no-header", action="store_true",
        help="Treat first row as data (generate column names)",
    )
    tbl.add_argument(
        "--stats", action="store_true",
        help="Show column statistics instead of data",
    )

    return p


def resolve_output(args: argparse.Namespace) -> str:
    """Determine output format from flags.

    Note: ``--stats`` is *not* an output format — it changes which table
    is rendered (the column-stats summary) but the rendering itself
    still goes through whichever format the user requested.
    """
    formats = ["csv", "tsv", "json", "markdown", "dkvp", "plain", "use_rich"]
    chosen = [f for f in formats if getattr(args, f, False)]
    if len(chosen) > 1:
        print(f"tabletop: only one output format allowed", file=sys.stderr)
        sys.exit(1)
    if chosen:
        return chosen[0]
    return "use_rich" if sys.stdout.isatty() else "plain"


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.sort and args.sort_reverse:
        print("tabletop: --sort and --sort-reverse are mutually exclusive", file=sys.stderr)
        sys.exit(1)

    # Read
    lines = read_input(args.file)
    table = parse(lines, has_header=not args.no_header)
    if not table:
        print("tabletop: no input data", file=sys.stderr)
        sys.exit(1)

    # Transforms (order matters)
    try:
        if args.sort:
            table = tf.sort_by(table, args.sort, reverse=False)
        if args.sort_reverse:
            table = tf.sort_by(table, args.sort_reverse, reverse=True)
        for filt in args.filter:
            if ":" not in filt:
                print(f"tabletop: invalid filter: {filt} (expected COL:PATTERN)", file=sys.stderr)
                sys.exit(1)
            col_spec, pattern = filt.split(":", 1)
            table = tf.filter_by(table, col_spec, pattern)
        if args.columns:
            specs = [s.strip() for s in args.columns.split(",")]
            table = tf.select_columns(table, specs)
        if args.remove:
            specs = [s.strip() for s in args.remove.split(",")]
            table = tf.remove_columns(table, specs)
        if args.head is not None:
            table = tf.head(table, args.head)
        if args.tail is not None:
            table = tf.tail(table, args.tail)
        if args.unique is not None:
            col = args.unique if args.unique else None
            table = tf.unique(table, col)
        if args.stats:
            table = tf.stats(table)
    except TabletopError as e:
        print(f"tabletop: {e}", file=sys.stderr)
        sys.exit(1)

    # Output
    mode = resolve_output(args)
    console = Console()

    if mode == "csv":
        fmt.csv_out(table)
    elif mode == "tsv":
        fmt.tsv_out(table)
    elif mode == "json":
        fmt.json_out(table)
    elif mode == "markdown":
        fmt.markdown_out(table)
    elif mode == "dkvp":
        fmt.dkvp_out(table)
    elif mode == "use_rich":
        fmt.rich(table, console)
    else:
        fmt.plain(table)


if __name__ == "__main__":
    main()
