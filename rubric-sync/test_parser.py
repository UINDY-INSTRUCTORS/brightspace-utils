#!/usr/bin/env python3
"""Test the RubricParser on actual rubric files."""

from pathlib import Path
from rubric_parser import RubricParser

FIXTURES = Path(__file__).parent / "tests" / "fixtures"


def test_abet_format():
    """Test parsing EENG-340 ABET rubric."""
    print("=" * 60)
    print("Testing ABET Format (EENG-340)")
    print("=" * 60)

    rubric_file = FIXTURES / "eeng-340-abet.md"
    if not rubric_file.exists():
        raise SystemExit(f"FAIL: fixture missing: {rubric_file}")

    content = rubric_file.read_text()
    parser = RubricParser()

    # Detect format
    detected_format = parser.detect_format(content)
    print(f"✓ Format detected: {detected_format}")

    # Parse
    rubric = parser.parse(content)
    assert rubric.num_criteria > 0, f"FAIL: parsed 0 criteria from {rubric_file}"

    print(f"✓ Title: {rubric.title}")
    print(f"✓ Format: {rubric.format}")
    print(f"✓ Total points: {rubric.total_points}")
    print(f"✓ Number of criteria: {rubric.num_criteria}")
    print(f"✓ Total weight: {rubric.total_weight:.2%}")

    print("\nCriteria:")
    for i, crit in enumerate(rubric.criteria, 1):
        print(f"\n  {i}. {crit.name}")
        print(f"     Weight: {crit.weight_pct}")
        print(f"     Levels: {', '.join(l.name for l in crit.levels)}")
        for level in crit.levels:
            print(f"       - {level.name} ({level.value}): {level.description[:60]}...")


def test_lab_format():
    """Test parsing PH-230 Lab rubric."""
    print("\n" + "=" * 60)
    print("Testing Lab Format (PH-230)")
    print("=" * 60)

    rubric_file = FIXTURES / "ph230-lab-sectioned.md"
    if not rubric_file.exists():
        raise SystemExit(f"FAIL: fixture missing: {rubric_file}")

    content = rubric_file.read_text()
    parser = RubricParser()

    # Detect format
    detected_format = parser.detect_format(content)
    print(f"✓ Format detected: {detected_format}")

    # Parse
    rubric = parser.parse(content)
    assert rubric.num_criteria > 0, f"FAIL: parsed 0 criteria from {rubric_file}"

    print(f"✓ Title: {rubric.title}")
    print(f"✓ Course: {rubric.course}")
    print(f"✓ Format: {rubric.format}")
    print(f"✓ Total points: {rubric.total_points}")
    print(f"✓ Number of criteria: {rubric.num_criteria}")
    print(f"✓ Total weight: {rubric.total_weight:.2%}")

    print("\nCriteria:")
    for i, crit in enumerate(rubric.criteria, 1):
        print(f"\n  {i}. {crit.name}")
        print(f"     Weight: {crit.weight_pct}")
        print(f"     Levels: {', '.join(l.name for l in crit.levels)}")
        if crit.keywords:
            print(f"     Keywords: {', '.join(crit.keywords)}")
        for level in crit.levels:
            print(f"       - {level.name} ({level.value}): {level.description[:60]}...")
            if level.indicators:
                for ind in level.indicators[:2]:  # Show first 2
                    print(f"         • {ind[:50]}...")


if __name__ == '__main__':
    test_abet_format()
    test_lab_format()
    print("\n" + "=" * 60)
    print("✅ Parser tests complete!")
    print("=" * 60)
