#!/usr/bin/env python3
"""
Convert RUBRIC.md files to Brightspace-importable ZIP packages.

Supports both ABET-style (single table) and Lab-style (sectioned) rubric formats.

Usage:
    python3 convert_rubric_to_d2l.py /path/to/RUBRIC.md --output my-rubric.zip
    python3 convert_rubric_to_d2l.py /path/to/RUBRIC.md  # Uses default output name
"""

import argparse
import sys
from pathlib import Path

from rubric_parser import RubricParser
from rubric_packager import RubricPackager


def main():
    parser = argparse.ArgumentParser(
        description='Convert RUBRIC.md to Brightspace-importable ZIP package',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  python3 convert_rubric_to_d2l.py eeng-340-rubric.md
  python3 convert_rubric_to_d2l.py ph230/RUBRIC.md --output ph230-p03.zip
  python3 convert_rubric_to_d2l.py ph280/RUBRIC.md --output ~/Downloads/ph280.zip
        '''
    )

    parser.add_argument('rubric_file', help='Path to RUBRIC.md file')
    parser.add_argument(
        '-o', '--output',
        help='Output ZIP file path (default: <rubric_name>.zip in current directory)'
    )
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Verbose output'
    )
    parser.add_argument(
        '--no-scoring',
        action='store_true',
        help='Don\'t specify overall scoring thresholds (handle scoring in Brightspace manually)'
    )

    args = parser.parse_args()

    try:
        rubric_path = Path(args.rubric_file).resolve()
        if not rubric_path.exists():
            print(f"❌ Error: File not found: {rubric_path}", file=sys.stderr)
            sys.exit(1)

        if args.verbose:
            print(f"📄 Reading: {rubric_path}")

        # Read and parse
        content = rubric_path.read_text()
        parser_obj = RubricParser()
        rubric_data = parser_obj.parse(content)

        if args.verbose:
            print(f"✓ Format: {rubric_data.format}")
            print(f"✓ Title: {rubric_data.title}")
            print(f"✓ Criteria: {rubric_data.num_criteria}")
            print(f"✓ Total weight: {rubric_data.total_weight:.0%}")

        # Determine output path
        if args.output:
            output_path = Path(args.output).resolve()
        else:
            # Default: rubric_name.zip in current directory
            output_name = rubric_path.stem + '.zip'
            output_path = Path.cwd() / output_name

        if args.verbose:
            print(f"📦 Creating package: {output_path}")

        # Create package
        if args.verbose:
            if args.no_scoring:
                print(f"📊 No scoring thresholds (unspecified in Brightspace)")
            else:
                print(f"📊 Using 0-3 scale with default thresholds")

        packager = RubricPackager(
            rubric_data,
            use_scoring=not args.no_scoring
        )
        result_path = packager.create_package(output_path)

        print(f"✅ Success! Created: {result_path}")
        print(f"   File size: {result_path.stat().st_size:,} bytes")
        print(f"\nImport into Brightspace:")
        print(f"   1. Open your course > Course Tools > Import/Export/Copy Components")
        print(f"   2. Click 'Import' > select this ZIP file")
        print(f"   3. Click 'Import' and the rubric will be added to your course")

    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
