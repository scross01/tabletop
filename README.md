# tabletop

![tabletop demo](tabletop-demo.gif)

Reformat, sort, filter, and reshape space-aligned CLI table output.

Many CLI tools (`ollama list`, `df -h`, `netstat`, `docker ps`) output
tables with columns aligned using multiple spaces. These are hard to
sort, filter, or pipe into other tools. **tabletop** parses this output,
applies transforms, and re-renders it as a clean table in multiple
formats.

## Install

```bash
uv tool install https://github.com/scross01/tabletop.git
```

## Usage

```txt
usage: tabletop [-h] [--version] [--plain] [--rich] [--csv] [--tsv] [--json]
                [--markdown] [--dkvp] [-s COL] [-sr COL] [-f COL:PAT]
                [-c COLS] [-r COLS] [-H N] [-T N] [-u [COL]] [--no-header]
                [--stats]
                [FILE]

Reformat, sort, filter, and reshape space-aligned CLI tables.

positional arguments:
  FILE                  Input file (default: stdin)

options:
  -h, --help            show this help message and exit
  --version             show program's version number and exit

output formats:
  --plain               space-aligned table (default when piped)
  --rich                Rich formatted table (default in terminal)
  --csv                 CSV output
  --tsv                 TSV output
  --json                JSON array of objects
  --markdown, --md      Markdown table
  --dkvp                DKVP (key=value) output

transforms:
  -s COL, --sort COL    Sort ascending by column (name or 1-based index)
  -sr COL, --sort-reverse COL
                        Sort descending by column
  -f COL:PAT, --filter COL:PAT
                        Keep rows where column matches regex (repeatable)
  -c COLS, --columns COLS
                        Show only these columns (comma-separated names or
                        indices)
  -r COLS, --remove COLS
                        Remove these columns (comma-separated names or
                        indices)
  -H N, --head N        Keep only first N rows
  -T N, --tail N        Keep only last N rows
  -u [COL], --unique [COL]
                        Deduplicate rows (optionally by column)

table options:
  --no-header           Treat first row as data (generate column names)
  --stats               Show column statistics instead of data
```


## Quick start

```bash
# Pipe any space-aligned table
df -h | tabletop

# Sort columns with smart unit detection
df -h | tabletop -sr Used

# Export to CSV, JSON, Markdown
df -h | tabletop --csv
df -h | tabletop --json
df -h | tabletop --markdown
```

You can alias tabletop with your favorite format and other settings for quick and consistent usage.

```bash
alias tt=tabletop --rich

ps -eaf | tt -c PID,CMD
```

## Smart numerical unit detection

**tabletop** detects size units (MB, GB, KiB, etc.) and time periods ("8 hours ago") automatically,
parses them to their numeric values, and sorts correctly — so "270 MB" comes before "1.8 GB" as expected.


## CLI reference

```
tabletop [OPTIONS] [FILE]
```

**Positional arguments:**

| Argument | Description |
|----------|-------------|
| `FILE`   | Input file (default: stdin) |

**Output formats:**

| Flag | Description |
|------|-------------|
| `--plain` | Space-aligned table (default when piped) |
| `--rich` | Rich formatted table (default in terminal) |
| `--csv` | CSV output |
| `--tsv` | TSV output |
| `--json` | JSON array of objects |
| `--markdown`, `--md` | Markdown table |
| `--dkvp` | DKVP key=value pairs |

**Transforms:**

| Flag | Description |
|------|-------------|
| `-s`, `--sort COL` | Sort ascending by column (name or 1-based index) |
| `-sr`, `--sort-reverse COL` | Sort descending by column |
| `-f`, `--filter COL:PAT` | Keep rows where column matches regex (repeatable) |
| `-c`, `--columns COLS` | Show only these columns (comma-separated) |
| `-r`, `--remove COLS` | Remove these columns (comma-separated) |
| `-H`, `--head N` | Keep only first N rows |
| `-T`, `--tail N` | Keep only last N rows |
| `-u`, `--unique [COL]` | Deduplicate rows (optionally by column) |

**Table options:**

| Flag | Description |
|------|-------------|
| `--no-header` | Treat first row as data (auto-generate column names) |
| `--stats` | Show column statistics instead of data |
| `--version` | Show version |

## Updating

After editing source:

```bash
uv tool update tabletop
```
