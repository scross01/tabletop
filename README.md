# tabletop

Reformat, sort, filter, and reshape space-aligned CLI table output.

Many CLI tools (`ollama list`, `df -h`, `netstat`, `docker ps`) output
tables with columns aligned using multiple spaces. These are hard to
sort, filter, or pipe into other tools. **tabletop** parses this output,
applies transforms, and re-renders it as a clean table in multiple
formats.

```
$ ollama list | tabletop -f "name:gemma" -sr size -c name,size

NAME                   SIZE
---------------------  ------
gemma4:e4b             9.6 GB
gemma4:12b             7.6 GB
gemma4:e2b             7.2 GB
embeddinggemma:latest  621 MB
```

## Install

```bash
cd ~/Development/tabletop
uv sync
uv tool install --editable .
```

## Quick start

```bash
# Pipe any space-aligned table
ollama list | tabletop

# Sort, filter, select columns
ollama list | tabletop -s size -f "name:gemma" -c name,size

# Export to CSV, JSON, Markdown
ollama list | tabletop --csv
ollama list | tabletop --json
ollama list | tabletop --markdown
```

## How it works

Parses space-aligned tables by splitting columns on 2+ consecutive
spaces. Single spaces within fields are preserved:

```
Input:   lfm2.5:8b   9cf756159fc2   5.2 GB   8 hours ago
Parse:   ["lfm2.5:8b", "9cf756159fc2", "5.2 GB", "8 hours ago"]
                                  ↑                    ↑
                           single space           single space
                           preserved              preserved
```

This means "5.2 GB" and "7 hours ago" stay as single fields.

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

## Examples

### Sorting

```bash
# By column name
ollama list | tabletop -s name

# By column index (1-based)
ollama list | tabletop -s 3

# Descending
ollama list | tabletop -sr size

# Numeric-aware: "270 MB" sorts before "1.8 GB"
ollama list | tabletop -s size
```

### Filtering (regex)

```bash
# Exact match
ollama list | tabletop -f "name:gemma4:12b"

# Partial match
ollama list | tabletop -f "name:gemma"

# Alternation
ollama list | tabletop -f "name:gemma|granite"

# Case-insensitive (always)
ollama list | tabletop -f "name:GEMMA"

# Multiple filters (AND logic)
ollama list | tabletop -f "name:gemma" -f "size:GB"

# Filter by column index
ollama list | tabletop -f "3:GB"
```

### Column selection

```bash
# Keep columns by name
ollama list | tabletop -c name,size,modified

# Keep columns by index
ollama list | tabletop -c 1,3,4

# Remove columns
ollama list | tabletop -r id

# Mix names and indices
ollama list | tabletop -c name,3
```

### Slicing

```bash
# First 5 rows
ollama list | tabletop -H 5

# Last 3 rows
ollama list | tabletop -T 3

# First 5, then last 2 of those
ollama list | tabletop -H 5 -T 2
```

### Deduplication

```bash
# Remove duplicate rows
tabletop data.txt -u

# Deduplicate by column
ollama list | tabletop -u name
```

### Statistics

```bash
# Column stats: row count, unique values, samples
ollama list | tabletop --stats

# Output:
# ┏━━━━━━━━━━┳━━━━━━┳━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
# ┃ COLUMN   ┃ ROWS ┃ UNIQUE ┃ SAMPLES                      ┃
# ┡━━━━━━━━━━╇━━━━━━╇━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
# │ NAME     │ 13   │ 13     │ lfm2.5:8b, smollm2:1.7b, .. │
# │ SIZE     │ 13   │ 13     │ 5.2 GB, 1.8 GB, 270 MB      │
# └──────────┴──────┴────────┴──────────────────────────────┘
```

### Output formats

```bash
# CSV
ollama list | tabletop --csv

# TSV
ollama list | tabletop --tsv

# JSON
ollama list | tabletop --json

# Markdown
ollama list | tabletop --markdown

# DKVP (key=value)
ollama list | tabletop --dkvp
```

### Combining transforms

Transforms are applied in this order:

1. Sort
2. Filter
3. Column selection/removal
4. Head/tail
5. Unique
6. Stats

```bash
# Filter gemma models, sort by size descending, show only name and size
ollama list | tabletop -f "name:gemma" -sr size -c name,size

# Find largest 3 models
ollama list | tabletop -s size -T 3

# Filter, sort, select, export to JSON
ollama list | tabletop -f "size:GB" -sr size -c name,size --json
```

### Reading from files

```bash
# From a file
tabletop data.txt

# From a file with transforms
tabletop data.txt -s 2 -c 1,3
```

## Best results with

`tabletop` works best with consistently aligned output where columns are
separated by 2+ spaces:

```bash
# Good (consistent alignment)
ollama list
df -h
netstat -rn
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Image}}"
ls -la
```

Commands that use single-space separation between some columns
(like `ps aux`) may have fields merged. For `ps`, use explicit formatting:

```bash
ps -eo pid,user,%cpu,%mem,rss,comm --sort=-%cpu | tabletop
```

## Updating

After editing source:

```bash
cd ~/Development/tabletop
uv sync
uv tool install --editable . --force
```

## Project structure

```
tabletop/
├── pyproject.toml          # Project config, dependencies
├── README.md               # This file
├── tabletop/
│   ├── __init__.py
│   ├── cli.py              # CLI argument parsing, main()
│   ├── parser.py           # Space-aligned table parser
│   ├── transforms.py       # Sort, filter, column ops
│   └── output.py           # Rich, plain, CSV, TSV, JSON formatters
└── .venv/                  # Virtual environment
```
