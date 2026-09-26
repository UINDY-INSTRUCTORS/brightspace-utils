"""Parser for RUBRIC.md files in both ABET and Lab formats."""

import re
from typing import Optional, List, Tuple
from rubric_data import RubricData, Criterion, Level


class RubricParser:
    """Detects and parses RUBRIC.md files in either ABET or Lab format."""

    def detect_format(self, markdown_text: str) -> str:
        """
        Detect whether this is ABET format (single table) or Lab format (sections).

        Returns:
            'abet' or 'lab'
        """
        # Lab format has "## Criterion N:" headers
        if re.search(r'##\s+Criterion\s+\d+:', markdown_text):
            return 'lab'

        # ABET format has a markdown table with ABET-style columns
        # Look for table with "Report Section" or similar ABET indicators
        if re.search(r'\|\s*#\s*\|.*Report Section.*\|', markdown_text):
            return 'abet'

        # Fallback: if it has criterion headers, assume lab; otherwise abet
        if '## Criterion' in markdown_text:
            return 'lab'

        return 'abet'

    def parse(self, markdown_text: str) -> RubricData:
        """
        Parse RUBRIC.md and return format-agnostic RubricData.

        Args:
            markdown_text: The full markdown content of a RUBRIC.md file

        Returns:
            RubricData object with all criteria and levels
        """
        format = self.detect_format(markdown_text)

        if format == 'abet':
            return self.parse_abet(markdown_text)
        else:
            return self.parse_lab(markdown_text)

    def parse_abet(self, markdown_text: str) -> RubricData:
        """
        Parse ABET-style rubric (single markdown table).

        Expected format:
        ## EENG-340 Generic Project Rubric

        | # | Report Section | % | E (...) | S (...) | D (...) | U (...) |
        | --- | --- | --- | --- | --- | --- | --- |
        | **1** | **Intro** | 5 | Excellence... | Satisfactory... | Developing... | Unsatisfactory... |
        """
        rubric = RubricData(title="", format='abet', total_points=100)

        # Extract title from first heading
        title_match = re.search(r'^#+\s+(.+?)$', markdown_text, re.MULTILINE)
        if title_match:
            rubric.title = title_match.group(1).strip()

        # Find the markdown table
        # Tables have rows starting with |
        table_rows = [line.strip() for line in markdown_text.split('\n') if line.strip().startswith('|')]

        if not table_rows:
            raise ValueError("No markdown table found in ABET rubric")

        # Parse table rows (skip separator rows that are all dashes)
        criteria = []
        for row in table_rows[2:]:  # Skip header and separator
            if not row or '---' in row or row.count('|') < 7:
                continue

            parts = [p.strip() for p in row.split('|')[1:-1]]  # Remove empty first/last
            if len(parts) < 7:
                continue

            # Format: # | Name | % | E | S | D | U
            try:
                criterion_num = parts[0].replace('**', '').strip()
                criterion_name = parts[1].replace('**', '').strip()
                weight_str = parts[2].strip()

                # Skip total row
                if 'Total' in criterion_name:
                    continue

                weight = float(weight_str) / 100.0  # Convert % to decimal

                # Extract ABET code from name if present (e.g., "Problem (1a)" -> keep it)
                criterion_name_clean = re.sub(r'\s*\(\d+[a-z]*\)\s*', lambda m: f" {m.group(0).strip()}", criterion_name)

                e_desc = parts[3].strip()
                s_desc = parts[4].strip()
                d_desc = parts[5].strip()
                u_desc = parts[6].strip()

                # Create levels: E=3, S=2, D=1, U=0
                levels = [
                    Level(name='Exemplary', value=3.0, description=e_desc),
                    Level(name='Satisfactory', value=2.0, description=s_desc),
                    Level(name='Developing', value=1.0, description=d_desc),
                    Level(name='Unsatisfactory', value=0.0, description=u_desc),
                ]

                criterion = Criterion(
                    name=criterion_name_clean,
                    weight=weight,
                    weight_pct=weight_str + '%',
                    levels=levels
                )
                criteria.append(criterion)
            except (ValueError, IndexError) as e:
                # Skip rows that don't parse correctly
                continue

        rubric.criteria = criteria
        return rubric

    def parse_lab(self, markdown_text: str) -> RubricData:
        """
        Parse Lab-style rubric (sectioned format with rich metadata).

        Expected format:
        # PHYS/MENG 230 - Lab Report Rubric

        **Course**: PHYS/MENG 230
        **Total Points**: 100

        ## Criterion 1: Abstract & Description (10%)

        Explanation text...

        ### Performance Levels

        | Level | Points | Description |
        | Excellent | 7-10 | ... |
        | Good | 4-6 | ... |
        | Poor | 0-3 | ... |

        ### Excellent Indicators
        - Bullet 1
        - Bullet 2

        ### Good Indicators
        ...
        """
        rubric = RubricData(title="", format='lab', total_points=100)

        # Extract title from first heading
        title_match = re.search(r'^#\s+(.+?)$', markdown_text, re.MULTILINE)
        if title_match:
            rubric.title = title_match.group(1).strip()

        # Extract metadata
        course_match = re.search(r'\*\*Course\*\*:\s*(.+?)(?:\n|$)', markdown_text)
        if course_match:
            rubric.course = course_match.group(1).strip()

        points_match = re.search(r'\*\*Total Points\*\*:\s*(\d+)', markdown_text)
        if points_match:
            rubric.total_points = int(points_match.group(1))

        # Split by criterion sections
        criterion_pattern = r'##\s+Criterion\s+\d+:\s+(.+?)\s*\((\d+)%\)'
        criterion_sections = re.split(r'(?=##\s+Criterion\s+\d+:)', markdown_text)

        criteria = []
        for section in criterion_sections[1:]:  # Skip content before first criterion
            criterion = self._parse_criterion_section(section)
            if criterion:
                criteria.append(criterion)

        rubric.criteria = criteria
        return rubric

    def _parse_criterion_section(self, section: str) -> Optional[Criterion]:
        """Parse a single criterion section from lab format."""

        # Extract criterion name and weight
        header_match = re.search(r'##\s+Criterion\s+\d+:\s+(.+?)\s*\((\d+)%\)', section)
        if not header_match:
            return None

        name = header_match.group(1).strip()
        weight = float(header_match.group(2)) / 100.0
        weight_pct = header_match.group(2) + '%'

        # Extract purpose (text before "### Performance Levels")
        purpose = None
        purpose_match = re.search(
            r'##\s+Criterion\s+\d+:.+?(?=###\s+Performance Levels)',
            section,
            re.DOTALL
        )
        if purpose_match:
            purpose_text = purpose_match.group(0)
            # Remove the header line
            purpose_lines = purpose_text.split('\n')[1:]
            purpose_text = '\n'.join(purpose_lines).strip()
            # Remove empty lines and performance levels marker
            if purpose_text and not purpose_text.startswith('###'):
                purpose = purpose_text

        # Find performance levels table
        levels = []
        perf_levels_match = re.search(
            r'###\s+Performance Levels\s*\n\n(.*?)(?=###|$)',
            section,
            re.DOTALL
        )
        if perf_levels_match:
            table_text = perf_levels_match.group(1)
            levels = self._parse_performance_table(table_text)

        if not levels:
            return None

        # Extract indicators by level
        indicators_by_level = {}
        for level_name in ['Excellent', 'Good', 'Poor']:
            indicators_pattern = rf'###\s+{level_name}\s+Indicators\s*\n(.*?)(?=###|##|$)'
            indicators_match = re.search(indicators_pattern, section, re.DOTALL)
            if indicators_match:
                bullet_lines = [
                    line.strip().lstrip('-*').strip()
                    for line in indicators_match.group(1).split('\n')
                    if line.strip().startswith('-') or line.strip().startswith('*')
                ]
                indicators_by_level[level_name] = bullet_lines

        # Attach indicators to levels
        for level in levels:
            level.indicators = indicators_by_level.get(level.name, [])

        # Extract keywords
        keywords = []
        keywords_match = re.search(r'###\s+Keywords\s*\n(.+?)(?=\n###|\n##|$)', section, re.DOTALL)
        if keywords_match:
            keyword_text = keywords_match.group(1).strip()
            keywords = [k.strip() for k in keyword_text.split(',')]

        # Extract common issues
        common_issues = []
        issues_match = re.search(r'###\s+Common Issues\s*\n(.*?)(?=###|##|$)', section, re.DOTALL)
        if issues_match:
            bullet_lines = [
                line.strip().lstrip('-*').strip()
                for line in issues_match.group(1).split('\n')
                if line.strip().startswith('-') or line.strip().startswith('*')
            ]
            common_issues = bullet_lines

        return Criterion(
            name=name,
            weight=weight,
            weight_pct=weight_pct,
            purpose=purpose,
            levels=levels,
            keywords=keywords,
            common_issues=common_issues
        )

    def _parse_performance_table(self, table_text: str) -> List[Level]:
        """Parse the Performance Levels markdown table."""
        levels = []
        rows = [line.strip() for line in table_text.split('\n') if line.strip().startswith('|')]

        # Skip header and separator rows
        for row in rows[2:]:
            parts = [p.strip() for p in row.split('|')[1:-1]]
            if len(parts) < 3:
                continue

            level_name = parts[0].replace('**', '').strip()
            points_str = parts[1].strip()
            description = parts[2].strip()

            # Map level names and values
            if level_name == 'Excellent':
                value = 3.0
            elif level_name == 'Good':
                value = 2.0
            elif level_name in ['Poor', 'Developing']:
                value = 1.0
            else:
                value = 0.0

            levels.append(Level(
                name=level_name,
                value=value,
                description=description
            ))

        return levels
