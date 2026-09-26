# Rubric-Sync Quick Reference

## One-Minute Setup

```bash
cd brightspace-utils/rubric-sync   # uv finds the project's pyproject.toml one level up
uv run convert_rubric_to_d2l.py /path/to/RUBRIC.md
```

Output: `rubric.zip` in current directory, ready to import to Brightspace.

## Scoring Options

Two ways to handle point values:

### Default: Simple 0-3 Scale (Recommended)
```bash
uv run convert_rubric_to_d2l.py RUBRIC.md
```
- Level values: Exemplary=3, Satisfactory=2, Developing=1, Unsatisfactory=0
- Overall thresholds: Exemplary 75%+, Good 50-74%, Developing 25-49%, Unsatisfactory <25%
- **Use this when:** You want Brightspace to auto-calculate overall scores

### Option: No Scoring Thresholds (Unspecified)
```bash
uv run convert_rubric_to_d2l.py RUBRIC.md --no-scoring
```
- Levels still have 0-3 values
- No overall_level_set (Brightspace uses defaults, or you configure manually)
- **Use this when:** You prefer to handle all grading setup yourself in Brightspace

## Import to Brightspace

1. Open your course → **Course Tools** → **Import/Export/Copy Components**
2. Click **Import**
3. Select the `.zip` file
4. Click **Import**
5. Rubric appears in your course (usually under **Assessments** → **Rubrics**)

## Examples

### EENG-340 (ABET format)
```bash
uv run convert_rubric_to_d2l.py \
  ~/Development/quarto_reports/build_quarto_reports/eeng-340-rubric.md \
  --output eeng340.zip
```

### PH-230 Project 8 (Lab format)
```bash
uv run convert_rubric_to_d2l.py \
  ~/Development/quarto_reports/ph230/p8-motors/.github/feedback/RUBRIC.md \
  --output ph230-p8.zip
```

### Batch Convert (manual loop)
```bash
for rubric in ~/Development/quarto_reports/ph230/*/. github/feedback/RUBRIC.md; do
  dir=$(dirname "$rubric")
  project=$(basename "$dir")
  uv run convert_rubric_to_d2l.py "$rubric" \
    --output "$project-rubric.zip"
done
```

## Troubleshooting

### "File not found" error
- Check the path is absolute or relative correctly
- Use `python3 -c "from pathlib import Path; print(Path('/your/path').resolve())"` to verify

### XML looks wrong / import fails
- Run with `-v` flag to see parsing details
- Check if RUBRIC.md follows expected format
- Look at `test_parser.py` for format examples

### Different criteria than expected
- Verify RUBRIC.md has proper criterion headers (ABET: table rows; Lab: `## Criterion N:` pattern)
- Check for typos in level names (must match expected: Exemplary/Excellent, Good, etc.)

## Format Quick Check

**Is it ABET?** If the rubric is a single markdown table with columns like `| # | Report Section | % | E | S | D | U |`

**Is it Lab?** If the rubric has sections like `## Criterion 1: Name (10%)` with performance tables below each.

## File Locations

| Course | Format | Path |
|--------|--------|------|
| EENG-340 | ABET | `build_quarto_reports/eeng-340-rubric.md` |
| EENG-310 | ? | `build_quarto_reports/eeng-310-rubric.md` |
| PH-230 | Lab | `ph230/p*/.github/feedback/RUBRIC.md` |
| PH-280 | Lab | `ph280/p*/.github/feedback/RUBRIC.md` |

## Output: What's in the ZIP?

Two files ready for Brightspace import:

1. **imsmanifest.xml** — Package metadata and resource references
2. **rubrics_d2l.xml** — The actual rubric in D2L schema v2011

Both files are required; they work together.

## Performance Levels Mapping

| Your RUBRIC.md | → | Brightspace |
|---|---|---|
| E (Exemplary) | → | Exemplary (value: 3) |
| S (Satisfactory) | → | Satisfactory (value: 2) |
| D (Developing) | → | Developing (value: 1) |
| U (Unsatisfactory) | → | Unsatisfactory (value: 0) |
| Excellent | → | Exemplary (value: 3) |
| Good | → | Satisfactory (value: 2) |
| Poor | → | Developing (value: 1) |

## Tips & Tricks

**View generated XML before import:**
```bash
unzip -l my-rubric.zip                    # See contents
unzip -p my-rubric.zip rubrics_d2l.xml   # Print XML to terminal
```

**Compare two rubrics:**
```bash
# Generate both
uv run convert_rubric_to_d2l.py rubric1.md -o rubric1.zip
uv run convert_rubric_to_d2l.py rubric2.md -o rubric2.zip

# Extract and diff XML
unzip -p rubric1.zip rubrics_d2l.xml > /tmp/r1.xml
unzip -p rubric2.zip rubrics_d2l.xml > /tmp/r2.xml
diff /tmp/r1.xml /tmp/r2.xml
```

**Validate the XML (basic):**
```bash
python3 -c "from xml.etree import ElementTree as ET; ET.parse('/tmp/rubrics_d2l.xml')" && echo "✓ Valid XML"
```

## Help & Support

- **Full documentation:** `README.md`
- **Implementation notes:** ``1. Projects/Brightspace-Rubric-Sync-Mapping.md` in the course vault (not public)`
- **Code tests:** `test_parser.py`, `test_converter.py`
- **Questions:** Check the mapping document or examine the source code in `rubric_*.py`
