"""Format detection and parsing for every supported RUBRIC.md shape."""

import zipfile
from pathlib import Path

import pytest

from rubric_packager import RubricPackager
from rubric_parser import RubricParser

FIXTURES = Path(__file__).parent / "fixtures"


def parse(name):
    return RubricParser().parse((FIXTURES / name).read_text())


@pytest.mark.parametrize("fixture, fmt, n_criteria", [
    ("eeng-340-abet.md", "abet", 9),
    ("ph230-lab-sectioned.md", "lab", 5),
    ("ph230-table-inline-weight.md", "table", 5),
    ("ph230-table-weight-column.md", "table", 5),
    ("phys230-table-multiline.md", "table", 5),
])
def test_detects_and_parses(fixture, fmt, n_criteria):
    rubric = parse(fixture)
    assert rubric.format == fmt
    assert rubric.num_criteria == n_criteria
    assert rubric.total_weight == pytest.approx(1.0)
    for c in rubric.criteria:
        assert c.levels, c.name
        assert all(l.description for l in c.levels), c.name


def test_table_levels_mapped_by_name_not_position():
    # Columns run Poor -> Excellent; levels must come out Excellent-first with the right values
    crit = parse("ph230-table-inline-weight.md").criteria[0]
    assert [(l.name, l.value) for l in crit.levels] == [
        ("Excellent", 3.0), ("Good", 2.0), ("Poor", 1.0)]
    assert crit.levels[0].description.startswith("Names sensor/motor")
    assert crit.levels[-1].description.startswith("Missing, vague")


def test_table_inline_weight_stripped_from_name():
    crit = parse("ph230-table-inline-weight.md").criteria[0]
    assert crit.name == "Abstract & Description"
    assert crit.weight_pct == "10%"


def test_table_weight_mid_label():
    names = [c.name for c in parse("phys230-table-multiline.md").criteria]
    assert "Results (including stats exercises)" in names


def test_table_weight_column():
    rubric = parse("ph230-table-weight-column.md")
    assert [c.weight_pct for c in rubric.criteria] == ["10%", "20%", "40%", "20%", "10%"]
    assert rubric.criteria[0].name == "Abstract & Description"


def test_table_multiline_rows_joined():
    crit = parse("phys230-table-multiline.md").criteria[0]
    excellent = crit.levels[0].description
    assert excellent.startswith("An abstract is present and is absolutely clear")
    assert "|" not in excellent


def test_grouped_subrows_fail_loudly():
    with pytest.raises(ValueError, match="no level descriptions"):
        parse("ph280-grouped-UNSUPPORTED.md")


def test_unrecognised_format_fails_loudly():
    with pytest.raises(ValueError, match="Unrecognised rubric format"):
        RubricParser().parse("# Notes\n\nJust some prose, no rubric table.\n")


@pytest.mark.parametrize("fixture", [
    "eeng-340-abet.md", "ph230-lab-sectioned.md",
    "ph230-table-inline-weight.md", "ph230-table-weight-column.md", "phys230-table-multiline.md",
])
def test_packages_to_importable_zip(fixture, tmp_path):
    out = RubricPackager(parse(fixture)).create_package(tmp_path / "rubric.zip")
    with zipfile.ZipFile(out) as z:
        assert set(z.namelist()) == {"imsmanifest.xml", "rubrics_d2l.xml"}
