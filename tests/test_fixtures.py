"""Smoke tests: verify real-world fixtures parse correctly."""


def test_ollama_fixture_loads(ollama_table):
    assert ollama_table.header == ["NAME", "ID", "SIZE", "MODIFIED"]
    assert len(ollama_table) == 12


def test_ollama_fixture_first_row(ollama_table):
    row = ollama_table.rows[0]
    assert row[0] == "lfm2.5:8b"
    assert row[1] == "9cf756159fc2"
    assert row[2] == "5.2 GB"
    assert row[3] == "10 hours ago"


def test_ollama_fixture_sizes_preserved(ollama_table):
    sizes = [r[2] for r in ollama_table.rows]
    assert "5.2 GB" in sizes
    assert "270 MB" in sizes
    assert "621 MB" in sizes


def test_ollama_fixture_long_names(ollama_table):
    names = [r[0] for r in ollama_table.rows]
    assert "llmvision/glimpse-v1:latest" in names


def test_hf_cache_fixture_loads(hf_cache_table):
    assert hf_cache_table.header == ["ID", "SIZE", "LAST_ACCESSED", "LAST_MODIFIED", "REFS"]
    assert len(hf_cache_table) == 4


def test_hf_cache_fixture_first_row(hf_cache_table):
    row = hf_cache_table.rows[0]
    assert row[0] == "model/BAAI/bge-small-en-v1.5"
    assert row[1] == "134.5M"
    assert row[4] == "main"


def test_hf_cache_fixture_trailing_summary_skipped(hf_cache_table):
    """The 'Found N repo(s)...' line should not appear in parsed rows."""
    for row in hf_cache_table.rows:
        assert not row[0].startswith("Found")


def test_hf_cache_fixture_separator_handled(hf_cache_table):
    """Separator line between header and data should be excluded."""
    for row in hf_cache_table.rows:
        assert not all(c == "-" for c in row[0])


# ── df -h ──

def test_df_fixture_loads(df_table):
    assert df_table.header == ["Filesystem", "Size", "Used", "Avail", "Capacity", "iused", "ifree", "%iused", "Mounted on"]
    assert len(df_table) > 0


def test_df_fixture_mounted_on(df_table):
    """Check that root filesystem mount point appears in the last column."""
    assert any(r[-1] == "/" for r in df_table.rows)


# ── lsof -i ──

def test_lsof_fixture_loads(lsof_table):
    assert "COMMAND" in lsof_table.header
    assert len(lsof_table) > 0


def test_lsof_fixture_columns(lsof_table):
    assert "PID" in lsof_table.header
    assert "NAME" in lsof_table.header


# ── podman images ──

def test_podman_images_loads(podman_images_table):
    assert "REPOSITORY" in podman_images_table.header
    assert len(podman_images_table) > 0


# ── podman volume ls ──

def test_podman_volume_loads(podman_volume_table):
    assert "VOLUME NAME" in podman_volume_table.header
    assert len(podman_volume_table) > 0


# ── ps aux ──

def test_ps_aux_loads(ps_aux_table):
    """Known edge case: TIME/COMMAND single-space gap causes column merging."""
    assert "USER" in ps_aux_table.header


# ── ps ef ──

def test_ps_ef_loads(ps_ef_table):
    assert "UID" in ps_ef_table.header
    assert len(ps_ef_table) > 0


# ── ps (standard) ──

def test_ps_loads(ps_table):
    """Known edge case: leading space in header causes merged columns."""
    assert any("PID" in h for h in ps_table.header)
    assert len(ps_table) > 0


# ── podman ps -a ──

def test_podman_ps_all_loads(podman_ps_all_table):
    assert "CONTAINER ID" in podman_ps_all_table.header
    assert len(podman_ps_all_table) == 1
