#!/usr/bin/env python3
"""Test the RubricToD2L converter."""

import tempfile
from pathlib import Path
from rubric_parser import RubricParser
from rubric_to_d2l import RubricToD2L

FIXTURES = Path(__file__).parent / "tests" / "fixtures"


def test_abet_conversion():
    """Test converting EENG-340 ABET rubric to D2L XML."""
    print("=" * 60)
    print("Testing ABET → D2L Conversion (EENG-340)")
    print("=" * 60)

    rubric_file = FIXTURES / "eeng-340-abet.md"
    content = rubric_file.read_text()

    # Parse
    parser = RubricParser()
    rubric = parser.parse(content)
    assert rubric.num_criteria > 0, f"FAIL: parsed 0 criteria from {rubric_file}"
    print(f"✓ Parsed: {rubric.title} ({rubric.num_criteria} criteria)")

    # Convert
    converter = RubricToD2L(rubric)
    xml = converter.generate_xml()

    # Write to temp file
    output_file = Path(tempfile.gettempdir()) / "eeng340_rubric.xml"
    output_file.write_text(xml)
    print(f"✓ Generated XML ({len(xml)} bytes)")
    print(f"✓ Saved to {output_file}")

    # Print first 2000 chars as sample
    print("\nXML Preview (first 2000 chars):")
    print("-" * 60)
    print(xml[:2000])
    print("...")


def test_lab_conversion():
    """Test converting PH-230 Lab rubric to D2L XML."""
    print("\n" + "=" * 60)
    print("Testing Lab → D2L Conversion (PH-230)")
    print("=" * 60)

    rubric_file = FIXTURES / "ph230-lab-sectioned.md"
    content = rubric_file.read_text()

    # Parse
    parser = RubricParser()
    rubric = parser.parse(content)
    assert rubric.num_criteria > 0, f"FAIL: parsed 0 criteria from {rubric_file}"
    print(f"✓ Parsed: {rubric.title} ({rubric.num_criteria} criteria)")

    # Convert
    converter = RubricToD2L(rubric)
    xml = converter.generate_xml()

    # Write to temp file
    output_file = Path(tempfile.gettempdir()) / "ph230_rubric.xml"
    output_file.write_text(xml)
    print(f"✓ Generated XML ({len(xml)} bytes)")
    print(f"✓ Saved to {output_file}")

    # Print first 2000 chars as sample
    print("\nXML Preview (first 2000 chars):")
    print("-" * 60)
    print(xml[:2000])
    print("...")


if __name__ == '__main__':
    test_abet_conversion()
    test_lab_conversion()
    print("\n" + "=" * 60)
    print("✅ Converter tests complete!")
    print("=" * 60)
