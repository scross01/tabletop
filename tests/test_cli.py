"""Tests for tabletop CLI (integration)."""

import subprocess
import sys


def run_tabletop(*args, input_data: str = "") -> subprocess.CompletedProcess:
    """Run tabletop with given args and input."""
    return subprocess.run(
        [sys.executable, "-m", "tabletop.cli", *args],
        input=input_data,
        capture_output=True,
        text=True,
        timeout=10,
    )


SAMPLE = """\
NAME    SIZE    MODIFIED
alpha   100 MB  1 day ago
beta    2.5 GB  2 days ago
gamma   50 MB   3 days ago
delta   1.0 GB  4 days ago
"""


class TestCLI:
    def test_basic(self):
        r = run_tabletop("--plain", input_data=SAMPLE)
        assert r.returncode == 0
        assert "NAME" in r.stdout
        assert "alpha" in r.stdout

    def test_sort_ascending(self):
        r = run_tabletop("-s", "2", "--plain", input_data=SAMPLE)
        assert r.returncode == 0
        lines = r.stdout.strip().split("\n")
        data_lines = [l for l in lines[1:]]  # skip header
        sizes = [l.split("  ")[1].strip() for l in data_lines if l.strip()]
        # 50 MB < 100 MB < 1.0 GB < 2.5 GB
        assert sizes[0] == "50 MB"
        assert sizes[-1] == "2.5 GB"

    def test_sort_descending(self):
        r = run_tabletop("-sr", "SIZE", "--plain", input_data=SAMPLE)
        assert r.returncode == 0
        lines = r.stdout.strip().split("\n")
        data_lines = [l for l in lines[1:] if l.strip()]
        sizes = [l.split("  ")[1].strip() for l in data_lines]
        assert sizes[0] == "2.5 GB"
        assert sizes[-1] == "50 MB"

    def test_filter(self):
        r = run_tabletop("-f", "NAME:alpha", "--plain", input_data=SAMPLE)
        assert r.returncode == 0
        assert "alpha" in r.stdout
        assert "beta" not in r.stdout

    def test_filter_regex(self):
        r = run_tabletop("-f", "SIZE:GB", "--plain", input_data=SAMPLE)
        assert r.returncode == 0
        assert "beta" in r.stdout  # 2.5 GB
        assert "delta" in r.stdout  # 1.0 GB
        assert "alpha" not in r.stdout  # 100 MB
        assert "gamma" not in r.stdout  # 50 MB

    def test_columns(self):
        r = run_tabletop("-c", "NAME,SIZE", "--plain", input_data=SAMPLE)
        assert r.returncode == 0
        assert "NAME" in r.stdout
        assert "SIZE" in r.stdout
        assert "MODIFIED" not in r.stdout

    def test_remove(self):
        r = run_tabletop("-r", "MODIFIED", "--plain", input_data=SAMPLE)
        assert r.returncode == 0
        assert "NAME" in r.stdout
        assert "MODIFIED" not in r.stdout

    def test_head(self):
        r = run_tabletop("-H", "2", "--plain", input_data=SAMPLE)
        assert r.returncode == 0
        lines = r.stdout.strip().split("\n")
        data_lines = [l for l in lines[1:] if l.strip()]
        assert len(data_lines) == 2

    def test_tail(self):
        r = run_tabletop("-T", "2", "--plain", input_data=SAMPLE)
        assert r.returncode == 0
        lines = r.stdout.strip().split("\n")
        data_lines = [l for l in lines[1:] if l.strip()]
        assert len(data_lines) == 2

    def test_csv(self):
        r = run_tabletop("--csv", input_data=SAMPLE)
        assert r.returncode == 0
        assert "NAME,SIZE,MODIFIED" in r.stdout

    def test_json(self):
        r = run_tabletop("--json", input_data=SAMPLE)
        assert r.returncode == 0
        assert '"NAME": "alpha"' in r.stdout

    def test_markdown(self):
        r = run_tabletop("--markdown", input_data=SAMPLE)
        assert r.returncode == 0
        assert "| NAME" in r.stdout

    def test_combine(self):
        r = run_tabletop(
            "-f", "SIZE:GB", "-sr", "SIZE", "-H", "1",
            "--plain", input_data=SAMPLE,
        )
        assert r.returncode == 0
        lines = r.stdout.strip().split("\n")
        data_lines = [l for l in lines[1:] if l.strip()]
        assert len(data_lines) == 1
        assert "2.5 GB" in data_lines[0]

    def test_version(self):
        r = run_tabletop("--version")
        assert r.returncode == 0
        assert "0.1.0" in r.stdout


def test_head_negative_rejected():
    r = run_tabletop("-H", "-1", input_data=SAMPLE)
    assert r.returncode != 0


def test_tail_negative_rejected():
    r = run_tabletop("-T", "-5", input_data=SAMPLE)
    assert r.returncode != 0


class TestCLINoHeader:
    def test_no_header(self):
        data = "alpha  100  x\nbeta   200  y\n"
        r = run_tabletop("--no-header", "--plain", input_data=data)
        assert r.returncode == 0
        assert "col1" in r.stdout
        assert "alpha" in r.stdout


class TestCLIStats:
    def test_stats(self):
        r = run_tabletop("--stats", input_data=SAMPLE)
        assert r.returncode == 0
        assert "COLUMN" in r.stdout
        assert "ROWS" in r.stdout
        assert "UNIQUE" in r.stdout
        assert "SAMPLES" in r.stdout


class TestCLIDkvp:
    def test_dkvp(self):
        r = run_tabletop("--dkvp", input_data=SAMPLE)
        assert r.returncode == 0
        assert "NAME=alpha" in r.stdout
        assert "SIZE=100 MB" in r.stdout


class TestCLIEdgeCases:
    def test_tab_separated_input(self):
        r = run_tabletop("--csv", input_data="A\tB\tC\n1\t2\t3\n")
        assert r.returncode == 0

    def test_single_column(self):
        r = run_tabletop("--plain", input_data="A\n1\n2\n")
        assert r.returncode == 0
        assert "A" in r.stdout
        assert "1" in r.stdout
