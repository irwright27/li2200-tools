# li2200-tools

Small Python tools for reading, editing, and writing LI-2200/LI-2200C text files.

The package parses a LI-2200 file into a structured `LI2200File` object, lets you
edit observation records with notebook-friendly selectors like `"A2"` and
`"B5:B8"`, then writes the result back to LI-2200 text format.

Package is useful for making fine-tuned changes to files after collection, giving added functionality to the FV-2200 software capabilities. This package is not yet capable of computing LAI, it is solely meant for editing/cleaning the txt file contents. Files should be input into FV-2200 for LAI computation.

## Status

This project is early-stage and focused on local data-cleaning workflows. The
core reader/writer and observation editing functions are usable, but the API may
still change as workflows become clearer.

## Installation

From the repository root:

```bash
pip install -e .
```


From GitHub:

```bash
pip install git+https://github.com/crop-sensing/li2200-tools.git
```

The project currently requires Python 3.13 or newer.

## Quick Start

```python
from li2200tools.io import read_li2200, write_li2200
from li2200tools.engine import (
    average_records,
    change_record,
    delete_records,
    filter_file,
    interpolate_above_records,
    rename_file,
)

file = read_li2200("raw/C1-4.TXT")

# Keep only selected records.
filtered = filter_file(file, records=["A1:A3", "B5:B8"])

# Keep only A and B records
filteredAB = filter_file(file, rec_type=["A","B"])

# Delete selected records.
cleaned = delete_records(file, records=["A2", "B7"])

# Average records into one computed record.
averaged = average_records(file, records=["A1:A3"], placement="first")

# Interpolate new A records before selected B records.
interpolated = interpolate_above_records(
    file,
    records=["A1:A4"],
    targets=["B4", "B6", "B8"],
    method="connect",
)

# Move/change a record's logical type or number.
changed = change_record(file, "A9", "B2")

# Write output. Optionally match LAI_FILE to output filename stem.
write_li2200(
    changed,
    "processed/C1-4_changed.TXT",
    header_match_filename=True,
)
```

## Record Selectors

Most editing functions accept a `records=` argument using compact selectors.
Selectors are 1-based logical positions within each record type, not physical
line numbers.

```python
"A2"            # second A record
"B5"            # fifth B record
["A1", "B3"]    # first A and third B
["A1:A3"]       # A1, A2, and A3
["A1:A3", "B5:B6"]
```

You can also pass actual `Record` objects if you already have them.

## Main Functions

### Reading and Writing

```python
file = read_li2200("input.TXT")
write_li2200(file, "output.TXT")
```

By default, `write_li2200()` will not overwrite an existing file. Pass
`overwrite=True` when you intentionally want to replace the output file:

```python
write_li2200(file, "output.TXT", overwrite=True)
```

Use `header_match_filename=True` to update the `LAI_FILE` header to match the
output filename without its extension:

```python
write_li2200(file, "processed/C1-4_changed.TXT", header_match_filename=True)
# LAI_FILE becomes C1-4_changed
```

### `filter_file`

Return a new file containing only selected observations.

```python
filtered = filter_file(file, records=["A1:A5", "B2"])
filtered = filter_file(file, rec_type="A")
filtered = filter_file(file, nA=[1, 3], nB="2:4")
```

### `delete_records`

Return a new file with selected observations removed.

```python
cleaned = delete_records(file, records=["A2", "B5:B7"])
```

### `average_records`

Average the timestamp and five ring values from selected records into one
computed record.

```python
averaged = average_records(
    file,
    records=["A1:A3"],
    placement="first",
    keep_inputs=False,
)
```

Ring values are averaged independently and rounded to the nearest hundredth.
The timestamp is averaged and formatted like the input timestamps.

Placement options:

- `"first"`: place at the first input record location. This is the default.
- `"last"`: place at the last input record location.
- `"beginning"`: place at the beginning of observations.
- `"end"`: place at the end of observations.

By default, input records are removed. Set `keep_inputs=True` to keep them.

### `interpolate_above_records`

Create computed A records before B records. Source records can be A or B records.
If `targets=None`, the function creates new A records before every B record.

```python
interpolated = interpolate_above_records(
    file,
    records=["A1:A4"],
    targets=["B4", "B6", "B8"],
    method="linear",
)
```

Interpolation methods:

- `"linear"`: fit one best-fit line per ring using time as x and ring value as y.
- `"connect"`: connect source records through time and interpolate between
  neighboring points. Targets before the first source timestamp use the first
  source values; targets after the last source timestamp use the last source
  values.

Use `remove_inputs=True` to remove the source records after creating the new A
records:

```python
interpolated = interpolate_above_records(
    file,
    records=["A1:A4"],
    method="connect",
    remove_inputs=True,
)
```

### `change_record`

Change a record's A/B type, logical number, or both.

```python
changed = change_record(file, "B7", "A6")
changed = change_record(file, "A9", "B2")
changed = change_record(file, "A7", "A6")
```

Changing logical position shifts later records of that type naturally. For
example, changing `A9` to `B2` makes the original `B2` become `B3`, the original
`B3` become `B4`, and so on.

Partial changes are also supported:

```python
change_record(file, "B7", "A")      # change type only
change_record(file, "A7", "6")      # change logical number only
change_record(file, "B7", record_type="A") # change type only (alternative syntax)
change_record(file, "A7", n=6)      # change logical number only (alternative syntax)

```

### `rename_file`

Change the `LAI_FILE` header value without changing the path on disk.

```python
renamed = rename_file(file, "C1-4_changed")
```

## Data Model

`read_li2200()` returns an immutable-style dataclass object:

```python
LI2200File(
    path=...,
    header=...,
    metadata=...,
    results=...,
    summary=...,
    sensors=...,
    observations=...,
)
```

Observation records are available at:

```python
file.observations.records
```

For A and B records, the five ring values are stored as:

```python
record.parsed["rings"]
```

The timestamp is stored as:

```python
record.parsed["dt"]
```

Editing functions return new `LI2200File` objects rather than modifying the
original object in place.

## Development

Run syntax checks with:

```bash
python -m compileall src/li2200tools
```

If `pytest` is installed, run tests with:

```bash
pytest
```

## Notes

- Original raw record lines are preserved when possible so filtered files do not
  unnecessarily change numeric formatting.
- Computed records are serialized from parsed values because they do not have
  original raw LI-2200 text lines.
- The parser currently focuses on the LI-2200 sections and observation record
  types used by this project.
