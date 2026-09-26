# Rubric-Sync: RUBRIC.md → Brightspace Converter

Convert your course rubrics to Brightspace-importable packages in seconds. Detects the rubric format automatically — ABET-style, sectioned lab-style, or condensed table.

## Quick Start

Run from `rubric-sync/` (or anywhere in the repo) — `uv run` uses the project's environment.

```bash
# Convert a single rubric (default: simple 0-3 scale)
uv run convert_rubric_to_d2l.py /path/to/RUBRIC.md

# Specify output location
uv run convert_rubric_to_d2l.py RUBRIC.md --output my-rubric.zip

# Verbose output (see parsing details)
uv run convert_rubric_to_d2l.py RUBRIC.md -v

# Don't specify scoring thresholds (let Brightspace use defaults)
uv run convert_rubric_to_d2l.py RUBRIC.md --no-scoring
```

## Supported Formats

### ABET Format (Single Table)
For ABET-aligned courses like EENG-340.

```markdown
## EENG-340 Generic Project Rubric

| # | Report Section | % | E (...) | S (...) | D (...) | U (...) |
| --- | --- | --- | --- | --- | --- | --- |
| **1** | **Intro** | 5 | Excellence... | Satisfactory... | Developing... | Unsatisfactory... |
```

**Features:**
- Simple markdown table format
- E/S/D/U performance levels (Exemplary/Satisfactory/Developing/Unsatisfactory)
- ABET codes in parentheses (1a, 1b, 7a, etc.)
- Compact descriptions in table cells

### Lab Format (Sectioned)
For lab courses like PH-230 and PH-280.

```markdown
# Course Title

**Course**: PHYS/MENG 230
**Total Points**: 100

## Criterion 1: Abstract & Description (10%)

Explanation of criterion purpose...

### Performance Levels

| Level | Points | Description |
|-------|--------|-------------|
| **Excellent** | 7-10 | ... |
| **Good** | 4-6 | ... |
| **Poor** | 0-3 | ... |

### Excellent Indicators
- Indicator 1
- Indicator 2

### Good Indicators
- Indicator 1

### Poor Indicators
- Indicator 1

### Keywords
keyword1, keyword2, keyword3

### Common Issues
- Issue 1
- Issue 2
```

**Features:**
- Sectioned by criterion
- 3-4 performance levels (Excellent/Good/Poor, + optional Unsatisfactory)
- Rich metadata: Indicators, Keywords, Common Issues
- Per-criterion point ranges and weights

### Condensed Table Format
Used by the newer PH-230 / PH-280 feedback rubrics (`ai-feedback-system/ph230-p*`, `ph280-p*`).

```markdown
# PHYS 230 P8: Sensor-Controlled Motors Rubric

**Course**: PHYS/MENG 230
**Total Points**: 100

| Section | Poor (0–35%) | Good (35–65%) | Excellent (65–100%) |
|---------|--------------|---------------|---------------------|
| **Abstract & Description (10%)** | ... | ... | ... |
```

**Features:**
- Detected by a header row whose columns (after the first) are all level names —
  Poor/Good/Excellent or Unsatisfactory/Developing/Satisfactory/Exemplary, **in any order**
- Weight inline in the criterion cell (`(10%)`, anywhere in the label) **or** in a trailing
  `Weight` column
- Rows may span several lines with indented ` |` continuations (the `phys-230-rubric.md`
  template style)

### Detection and failures

Detection order: `## Criterion N:` → Lab; `| # | Report Section |` → ABET; level-name header →
Table. Anything else is an **error**, as is a parse that yields 0 criteria — an empty rubric is
never packaged. The CLI also warns if criterion weights don't sum to 100%.

## How It Works

1. **Parser** (`rubric_parser.py`)
   - Detects rubric format automatically (ABET, Lab or Table)
   - Extracts criteria, performance levels, metadata
   - Returns normalized `RubricData` structure

2. **Converter** (`rubric_to_d2l.py`)
   - Converts `RubricData` → Brightspace XML
   - Normalizes performance levels to 4-level scale (3/2/1/0)
   - Appends rich metadata (indicators, keywords) to level descriptions
   - Includes criterion weights in names for visibility

3. **Packager** (`rubric_packager.py`)
   - Creates importable ZIP with `imsmanifest.xml` + `rubrics_d2l.xml`
   - Ready to import into Brightspace without modification

## Importing into Brightspace

1. Open your course → **Course Tools** → **Import/Export/Copy Components**
2. Click **Import**
3. Select the generated `.zip` file
4. Click **Import** — rubric appears in your course immediately

## Technical Details

### Performance Level Normalization

| Format | Level Name | → | Brightspace | Value |
|--------|-----------|---|-------------|-------|
| ABET | Exemplary (E) | → | Exemplary | 3 |
| ABET | Satisfactory (S) | → | Satisfactory | 2 |
| ABET | Developing (D) | → | Developing | 1 |
| ABET | Unsatisfactory (U) | → | Unsatisfactory | 0 |
| Lab | Excellent | → | Exemplary | 3 |
| Lab | Good | → | Satisfactory | 2 |
| Lab | Poor | → | Developing | 1 |
| Lab | (if present) | → | Unsatisfactory | 0 |

### Metadata Handling

**Lab format rich metadata is preserved:**
- Indicators appended to each level description
- Keywords stored in criterion metadata (visible on import)
- Common issues available for reference

**ABET format:**
- ABET codes preserved in criterion names
- Descriptions as-is

### Weight Storage

Criterion weights included in Brightspace criterion names for reference:
- `Introduction, background, purpose etc. (5%)`
- `Abstract & Description (10%)`

## File Structure

```
brightspace-utils/rubric-sync/
├── convert_rubric_to_d2l.py    # CLI entry point
├── rubric_parser.py             # Format detection + parsing
├── rubric_data.py               # Data classes (RubricData, Criterion, Level)
├── rubric_to_d2l.py             # XML generation
├── rubric_packager.py           # ZIP packaging
├── test_parser.py               # Parser tests
├── test_converter.py            # Converter tests
└── README.md                    # This file
```

## Testing

Run the test suite:

```bash
uv run pytest          # from anywhere in the repo
```

`tests/test_formats.py` covers every format and variant against the fixtures in
`tests/fixtures/`, including the shapes that must fail loudly.

Or test the full CLI:

```bash
uv run convert_rubric_to_d2l.py /path/to/RUBRIC.md -v
```

## Future Enhancements

- [ ] Batch conversion (multiple rubrics at once)
- [ ] Brightspace → RUBRIC.md (reverse sync)
- [ ] Per-course configuration file (weights, level mappings)
- [ ] Validation and dry-run mode
- [ ] Integration with GitHub Actions for auto-sync
- [ ] Web UI for conversion

## Known Limitations

- **Grouped sub-rows are not supported.** A table where a weighted group row has empty level
  cells and unweighted sub-items beneath it (e.g. `ph280/P01-rubric-coversheet.md`) raises an
  error rather than guessing how to split the weight. Fixture:
  `tests/fixtures/ph280-grouped-UNSUPPORTED.md`.
- **Tables without weights** (e.g. `RUBRIC_QUICK.md` quick-reference sheets) and numeric-level
  rubrics (`1 (unacceptable)` … with a score column) are rejected.
- **Multi-table ABET files** (e.g. separate pre-lab and post-lab tables) are merged into one
  rubric; the weight warning will flag the result.
- **Round-trip**: Exporting from Brightspace won't perfectly recreate original RUBRIC.md (acceptable, semantic equivalence maintained)
- **Level names**: Custom level names beyond E/S/D/U not yet supported (can be added)
- **Weights**: Brightspace stores weights in criterion names, not native weighting
- **Metadata**: Lab format indicators, keywords, common issues are appended to descriptions (not separately structured in D2L)

## License

Created for UIndy Physics courses. Use and modify freely.

## Questions?

See ``1. Projects/Brightspace-Rubric-Sync-Mapping.md` in the course vault (not public)` for implementation notes and design decisions.
