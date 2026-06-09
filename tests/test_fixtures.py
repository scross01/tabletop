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


# ── lsof -i (2-row short) ──

def test_lsof_short_header(lsof_short_table):
    """2-row lsof should detect all 9 columns correctly."""
    assert lsof_short_table.header == [
        "COMMAND", "PID", "USER", "FD", "TYPE",
        "DEVICE", "SIZE/OFF", "NODE", "NAME",
    ]
    assert lsof_short_table.ncols == 9


def test_lsof_short_row_count(lsof_short_table):
    """Both data rows should be parsed."""
    assert len(lsof_short_table) == 2


def test_lsof_short_first_row(lsof_short_table):
    """Row 0: syncthing, IPv6, port 8384."""
    row = lsof_short_table.rows[0]
    assert row[0] == "syncthing"
    assert row[1] == "946"
    assert row[2] == "stephen"
    assert row[3] == "47u"
    assert row[4] == "IPv6"
    assert row[5] == "0x2872210b88338af1"
    assert row[6] == "0t0"
    assert row[7] == "TCP"
    assert row[8] == "*:8384 (LISTEN)"


def test_lsof_short_second_row(lsof_short_table):
    """Row 1: Python, IPv4, localhost:http-alt."""
    row = lsof_short_table.rows[1]
    assert row[0] == "Python"
    assert row[1] == "36032"
    assert row[2] == "stephen"
    assert row[3] == "4u"
    assert row[4] == "IPv4"
    assert row[5] == "0xbbbf664c4ce01b69"
    assert row[6] == "0t0"
    assert row[7] == "TCP"
    assert row[8] == "localhost:http-alt (LISTEN)"


def test_lsof_short_sizeoff_not_empty(lsof_short_table):
    """SIZE/OFF column should have the '0t0' value, not be empty."""
    for row in lsof_short_table.rows:
        assert row[6] == "0t0"


def test_lsof_short_name_includes_listen(lsof_short_table):
    """NAME column should include the parenthetical (LISTEN)."""
    for row in lsof_short_table.rows:
        assert row[8].endswith("(LISTEN)")


def test_lsof_short_device_is_hex(lsof_short_table):
    """DEVICE column should be a hex address."""
    for row in lsof_short_table.rows:
        assert row[5].startswith("0x")


def test_lsof_short_columns_exist(lsof_short_table):
    """All expected lsof columns should be present."""
    expected = ["COMMAND", "PID", "USER", "FD", "TYPE", "DEVICE", "SIZE/OFF", "NODE", "NAME"]
    for col in expected:
        assert col in lsof_short_table.header, f"Missing column: {col}"


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
    """TIME/COMMAND single-space gap now correctly produces separate columns."""
    assert "USER" in ps_aux_table.header
    assert "TIME" in ps_aux_table.header
    assert "COMMAND" in ps_aux_table.header
    assert "TIME" in ps_aux_table.header and "COMMAND" in ps_aux_table.header
    # Verify TIME and COMMAND are distinct columns (not merged)
    time_idx = ps_aux_table.column_index("TIME")
    cmd_idx = ps_aux_table.column_index("COMMAND")
    assert time_idx is not None
    assert cmd_idx is not None
    assert time_idx != cmd_idx
    # Verify the first row's TIME and COMMAND values are separated
    if ps_aux_table.rows:
        row = ps_aux_table.rows[0]
        assert "3:25.56" in row[time_idx]
        assert "opencode" in row[cmd_idx]


# ── ps ef ──

def test_ps_ef_loads(ps_ef_table):
    assert "UID" in ps_ef_table.header
    assert "CMD" in ps_ef_table.header
    # TIME and CMD should be separate columns (not merged "TIME CMD")
    assert "TIME" in ps_ef_table.header
    time_idx = ps_ef_table.column_index("TIME")
    cmd_idx = ps_ef_table.column_index("CMD")
    assert time_idx is not None
    assert cmd_idx is not None
    assert time_idx != cmd_idx
    assert len(ps_ef_table) > 0


# ── ps (standard) ──

def test_ps_loads(ps_table):
    """Leading space / right-aligned headers now produce separate columns."""
    assert ps_table.header == ["PID", "TTY", "TIME", "CMD"]
    assert ps_table.ncols == 4
    assert len(ps_table) > 0
    # Verify first row values are in correct columns
    row = ps_table.rows[0]
    assert row[0] == "1234"  # PID
    assert row[1] == "??"    # TTY
    assert row[2] == "0:00.12"  # TIME
    assert "logd" in row[3]  # CMD


# ── podman ps -a ──

# ── ls -la (no-header) ──

def test_ls_la_loads(ls_la_table):
    """No-header parsing of ls -la should detect 9 columns."""
    assert ls_la_table.ncols == 9
    assert len(ls_la_table) > 0


def test_ls_la_columns(ls_la_table):
    """First row should correctly split permissions, links, owner, group, size, month, day, time, name."""
    row = ls_la_table.rows[0]
    assert row[0] == "drwxr-xr-x@"  # permissions
    assert row[3] == "staff"        # group
    assert row[7] == "14:31"        # time
    assert row[8] == "."            # filename


def test_ls_la_filenames_are_single_words(ls_la_table):
    """Rows with unquoted spaces in filenames are dropped as inconsistent."""
    # The fixture has 14 data rows. One has "test file.txt" (10 fields
    # instead of 9) and is filtered out. 13 rows remain.
    assert len(ls_la_table.rows) == 13  # 14 - 1 inconsistent row
    # All remaining filenames should be single words
    for row in ls_la_table.rows:
        assert " " not in row[-1]


def test_podman_ps_all_loads(podman_ps_all_table):
    assert "CONTAINER ID" in podman_ps_all_table.header
    assert len(podman_ps_all_table) == 1
