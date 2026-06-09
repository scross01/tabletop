"""Shared pytest fixtures for tabletop tests.

Loads real-world terminal output fixtures and provides parsed Tables.
"""

from pathlib import Path

import pytest

from tabletop.parser import parse

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _load(name: str) -> list[str]:
    """Load a fixture file as a list of lines."""
    return (FIXTURES_DIR / name).read_text().splitlines()


# ── ollama list ──────────────────────────────────────────────────────

@pytest.fixture
def ollama_lines():
    """Raw lines from `ollama list`."""
    return _load("ollama_list.txt")


@pytest.fixture
def ollama_table(ollama_lines):
    """Parsed Table from `ollama list`."""
    return parse(ollama_lines)


# ── hf cache list ────────────────────────────────────────────────────

@pytest.fixture
def hf_cache_lines():
    """Raw lines from `hf cache list`."""
    return _load("hf_cache_list.txt")


@pytest.fixture
def hf_cache_table(hf_cache_lines):
    """Parsed Table from `hf cache list` (separator + trailing summary handled)."""
    return parse(hf_cache_lines)


# ── df -h ─────────────────────────────────────────────────────

@pytest.fixture
def df_lines():
    return _load("df_h.txt")


@pytest.fixture
def df_table(df_lines):
    return parse(df_lines)


# ── lsof -i ───────────────────────────────────────────────────

@pytest.fixture
def lsof_lines():
    return _load("lsof_net.txt")


@pytest.fixture
def lsof_table(lsof_lines):
    return parse(lsof_lines)


# ── podman images ─────────────────────────────────────────────

@pytest.fixture
def podman_images_lines():
    return _load("podman_images.txt")


@pytest.fixture
def podman_images_table(podman_images_lines):
    return parse(podman_images_lines)


# ── podman volume ls ──────────────────────────────────────────

@pytest.fixture
def podman_volume_lines():
    return _load("podman_volume_ls.txt")


@pytest.fixture
def podman_volume_table(podman_volume_lines):
    return parse(podman_volume_lines)


# ── ps aux ────────────────────────────────────────────────────

@pytest.fixture
def ps_aux_lines():
    return _load("ps_aux.txt")


@pytest.fixture
def ps_aux_table(ps_aux_lines):
    return parse(ps_aux_lines)


# ── ps ef ─────────────────────────────────────────────────────

@pytest.fixture
def ps_ef_lines():
    return _load("ps_ef.txt")


@pytest.fixture
def ps_ef_table(ps_ef_lines):
    return parse(ps_ef_lines)


# ── ps (standard) ─────────────────────────────────────────────

@pytest.fixture
def ps_lines():
    return _load("ps.txt")


@pytest.fixture
def ps_table(ps_lines):
    return parse(ps_lines)


# ── podman ps -a ──────────────────────────────────────────────

@pytest.fixture
def podman_ps_all_lines():
    return _load("podman_ps_all.txt")


@pytest.fixture
def podman_ps_all_table(podman_ps_all_lines):
    return parse(podman_ps_all_lines)
