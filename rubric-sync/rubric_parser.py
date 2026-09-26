"""Parser for RUBRIC.md files in ABET, Lab and condensed-table formats."""

import re
from typing import Optional, List, Tuple
from rubric_data import RubricData, Criterion, Level


# Level-name keyword -> canonical value, checked in order. "Unsatisfactory" must
# come before "Satisfactory" since one contains the other.
LEVEL_VALUES = [
    ('unsatisfactory', 0.0),
    ('excellent', 3.0), ('exemplary', 3.0),
    ('good', 2.0), ('satisfactory', 2.0),
    ('poor', 1.0), ('developing', 1.0),
]


def level_value(header: str) -> Optional[float]:
    """Canonical value for a level column header like 'Good (35–65%)', or None."""
    h = header.replace('**', '').lower()
    for keyword, value in LEVEL_VALUES:
        if re.search(rf'\b{keyword}\b', h):
            return value
    return None


class RubricParser:
    """Detects and parses RUBRIC.md files in ABET, Lab or condensed-table format."""

    def detect_format(self, markdown_text: str) -> str:
        """
        Detect the rubric format.

        Returns:
            'lab'   - sectioned, "## Criterion N: Name (10%)" headers
            'abet'  - single table, "| # | Report Section | % | E | S | D | U |"
            'table' - single table, "| Section | Poor (...) | Good (...) | Excellent (...) |"
                      with weights inline in the criterion cell
        """
        # Lab format has "## Criterion N:" headers
        if re.search(r'##\s+Criterion\s+\d+:', markdown_text):
            return 'lab'

        # ABET format has a markdown table with ABET-style columns
        if re.search(r'\|\s*#?\s*\|.*Report Section.*\|', markdown_text):
            return 'abet'

        # Condensed table: a header row whose non-first columns are level names
        if self._find_level_table_header(markdown_text) is not None:
            return 'table'

        raise ValueError(
            "Unrecognised rubric format: expected '## Criterion N:' sections, an ABET "
            "'| # | Report Section |' table, or a table with level-name columns "
            "(Poor/Good/Excellent, E/S/D/U names)")

    def parse(self, markdown_text: str) -> RubricData:
        """
        Parse RUBRIC.md and return format-agnostic RubricData.

        Args:
            markdown_text: The full markdown content of a RUBRIC.md file

        Returns:
            RubricData object with all criteria and levels

        Raises:
            ValueError: if the format is unrecognised or no criteria are found,
                so an empty rubric is never packaged for import.
        """
        format = self.detect_format(markdown_text)

        if format == 'abet':
            rubric = self.parse_abet(markdown_text)
        elif format == 'table':
            rubric = self.parse_table(markdown_text)
        else:
            rubric = self.parse_lab(markdown_text)

        if rubric.num_criteria == 0:
            raise ValueError(f"Detected '{format}' format but parsed 0 criteria")
        return rubric

    WEIGHT_HEADER = re.compile(r'^(weight|%|percent|pct)$', re.IGNORECASE)

    def _find_level_table_header(self, markdown_text: str) -> Optional[Tuple[int, List[str]]]:
        """
        Line index and cells of the first table header shaped like
        | <criterion> | <level> | <level> | ... [| Weight |]
        i.e. every column after the first is a level name or a single weight column.
        """
        lines = markdown_text.split('\n')
        for i, line in enumerate(lines[:-1]):
            if not line.startswith('|'):
                continue
            if not re.match(r'^\s*\|[\s:|-]+\|\s*$', lines[i + 1]):  # next line must be a separator
                continue
            cells = [c.strip().replace('**', '') for c in line.strip().split('|')[1:-1]]
            rest = cells[1:]
            n_weight = sum(1 for c in rest if self.WEIGHT_HEADER.match(c))
            n_level = sum(1 for c in rest if level_value(c) is not None)
            if n_level >= 2 and n_weight <= 1 and n_level + n_weight == len(rest):
                return i, cells
        return None

    @staticmethod
    def _table_rows(lines: List[str], n_cols: int) -> List[List[str]]:
        """
        Collect the body rows of a table, joining multi-line rows.

        A row starts with '|' in column 0. Until it has all its cells, following
        lines (indented ' |' continuations, wrapped text, blank lines) belong to it.
        The table ends at the first line that is neither part of an unfinished row
        nor the start of a new one.
        """
        rows, current = [], None

        def complete(row: str) -> bool:
            return row.rstrip().endswith('|') and row.count('|') >= n_cols + 1

        for line in lines:
            if line.startswith('|') and (current is None or complete(current)):
                if current is not None:
                    rows.append(current)
                current = line
            elif current is not None and not complete(current):
                current += ' ' + line.strip()
            elif not line.strip():
                continue  # blank line between complete rows
            else:
                break
        if current is not None:
            rows.append(current)
        return [[c.strip() for c in r.strip().split('|')[1:-1]] for r in rows]

    def parse_table(self, markdown_text: str) -> RubricData:
        """
        Parse a condensed single-table rubric.

        Expected format:
        # PHYS 230 P8: Sensor-Controlled Motors Rubric

        **Course**: PHYS/MENG 230
        **Total Points**: 100

        | Section | Poor (0–35%) | Good (35–65%) | Excellent (65–100%) |
        |---------|--------------|---------------|---------------------|
        | **Abstract & Description (10%)** | ... | ... | ... |

        Also accepted:
        - the weight in its own column instead of the criterion cell
          (| Criterion | Poor | Good | Excellent | Weight |)
        - rows spread over several lines with indented ' |' continuations

        Level columns are mapped by name, not position, so any order works.
        """
        rubric = RubricData(title="", format='table', total_points=100)

        title_match = re.search(r'^#\s+(.+?)$', markdown_text, re.MULTILINE)
        if title_match:
            rubric.title = title_match.group(1).strip()

        course_match = re.search(r'\*\*Course\*\*:\s*(.+?)(?:\n|$)', markdown_text)
        if course_match:
            rubric.course = course_match.group(1).strip()

        points_match = re.search(r'\*\*Total Points\*\*:\s*(\d+)', markdown_text)
        if points_match:
            rubric.total_points = int(points_match.group(1))

        header_idx, header = self._find_level_table_header(markdown_text)
        weight_col = next((j for j, h in enumerate(header) if j and self.WEIGHT_HEADER.match(h)), None)
        # Level name shown in Brightspace: the header minus its score range, e.g. "Good"
        level_cols = [(j, re.sub(r'\s*\(.*?\)\s*', '', h).strip(), level_value(h))
                      for j, h in enumerate(header) if j and j != weight_col]

        lines = markdown_text.split('\n')
        criteria = []
        for cells in self._table_rows(lines[header_idx + 2:], len(header)):
            if len(cells) != len(header):
                raise ValueError(f"Row has {len(cells)} cells, header has {len(header)}: {cells[0][:50]!r}")

            label = cells[0].replace('**', '').strip()
            if re.match(r'^total\b', label, re.IGNORECASE):
                continue

            if weight_col is not None:
                weight_match = re.search(r'(\d+(?:\.\d+)?)\s*%?', cells[weight_col])
                name = label
            else:
                # "(10%)" anywhere in the label, e.g. "Results (20%) (including stats exercises)"
                weight_match = re.search(r'\((\d+(?:\.\d+)?)\s*%\)', label)
                name = re.sub(r'\s+', ' ', label[:weight_match.start()] + label[weight_match.end():]).strip() \
                    if weight_match else label
            if not weight_match:
                raise ValueError(f"No weight found for criterion {label!r}")
            weight_str = weight_match.group(1)

            descriptions = [cells[j] for j, _, _ in level_cols]
            if not any(descriptions):
                # e.g. a group heading row with sub-criteria beneath it - not a shape
                # this parser can map onto Brightspace without inventing weights
                raise ValueError(f"Criterion {name!r} has no level descriptions "
                                 "(grouped sub-rows are not supported)")

            levels = [Level(name=level_name, value=value, description=desc)
                      for (_, level_name, value), desc in zip(level_cols, descriptions)]
            levels.sort(key=lambda l: l.value, reverse=True)

            criteria.append(Criterion(
                name=name,
                weight=float(weight_str) / 100.0,
                weight_pct=weight_str + '%',
                levels=levels,
            ))

        rubric.criteria = criteria
        return rubric

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
