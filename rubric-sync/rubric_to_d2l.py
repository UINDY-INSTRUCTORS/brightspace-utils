"""Convert RubricData to Brightspace (D2L) XML format."""

import uuid
from xml.etree import ElementTree as ET
from xml.dom import minidom
from rubric_data import RubricData, Criterion, Level


class RubricToD2L:
    """Convert format-agnostic RubricData to Brightspace XML."""

    def __init__(self, rubric_data: RubricData, use_scoring: bool = True):
        self.rubric = rubric_data
        self.level_ids = {}  # Map level names to numeric IDs
        self.use_scoring = use_scoring  # If False, don't specify overall level thresholds

    def generate_xml(self) -> str:
        """
        Generate Brightspace rubrics_d2l.xml content.

        Returns:
            XML string ready to be written to file
        """
        # Assign numeric level IDs
        self._assign_level_ids()

        # Create root element
        rubrics_elem = ET.Element('rubrics')
        rubrics_elem.set('schemaversion', 'v2011')

        # Create rubric element
        rubric_elem = self._create_rubric_element()
        rubrics_elem.append(rubric_elem)

        # Convert to pretty-printed XML string
        xml_str = minidom.parseString(ET.tostring(rubrics_elem)).toprettyxml(indent='  ')

        # Remove the XML declaration (we'll add it ourselves)
        lines = xml_str.split('\n')
        if lines[0].startswith('<?xml'):
            lines = lines[1:]

        # Remove blank lines
        lines = [line for line in lines if line.strip()]

        return '<?xml version="1.0" encoding="UTF-8"?>\n' + '\n'.join(lines)

    def _assign_level_ids(self):
        """Assign numeric IDs to each level based on canonical order."""
        # Levels are: Exemplary/Excellent (3), Good/Satisfactory (2), Poor/Developing (1), Unsatisfactory (0)
        id_counter = {3.0: 60000, 2.0: 60001, 1.0: 60002, 0.0: 60003}

        # Collect all unique level names and their values
        level_map = {}
        for criterion in self.rubric.criteria:
            for level in criterion.levels:
                if level.name not in level_map:
                    # Map level names to their canonical values
                    if level.value == 3.0:
                        level_map[level.name] = (3.0, 60000)
                    elif level.value == 2.0:
                        level_map[level.name] = (2.0, 60001)
                    elif level.value == 1.0:
                        level_map[level.name] = (1.0, 60002)
                    else:
                        level_map[level.name] = (0.0, 60003)

        self.level_ids = level_map

    def _create_rubric_element(self) -> ET.Element:
        """Create the main <rubric> element."""
        rubric_elem = ET.Element('rubric')

        # Attributes
        rubric_elem.set('id', '1')
        rubric_elem.set('resource_code', str(uuid.uuid4()))
        rubric_elem.set('name', self.rubric.title)
        rubric_elem.set('type', '1')
        rubric_elem.set('scoring_method', '0')
        rubric_elem.set('display_levels_in_des_order', 'True')
        rubric_elem.set('state', '0')
        rubric_elem.set('visibility', '0')
        rubric_elem.set('uses_overall_score', 'True')
        rubric_elem.set('has_manual_alignment', 'False')
        rubric_elem.set('score_visible_to_assessed_users', 'True')
        rubric_elem.set('enabled_feedback_copy', 'False')

        # Description (optional)
        desc_elem = ET.SubElement(rubric_elem, 'description')
        desc_elem.set('text_type', 'text/html')
        text_elem = ET.SubElement(desc_elem, 'text')
        text_elem.text = ''

        # Criteria groups
        criteria_groups_elem = ET.SubElement(rubric_elem, 'criteria_groups')
        criteria_group_elem = self._create_criteria_group()
        criteria_groups_elem.append(criteria_group_elem)

        # Overall level set (only if use_scoring is True)
        if self.use_scoring:
            overall_level_set_elem = self._create_overall_level_set()
            rubric_elem.append(overall_level_set_elem)

        return rubric_elem

    def _create_criteria_group(self) -> ET.Element:
        """Create <criteria_group> with levels and criteria."""
        cg_elem = ET.Element('criteria_group')
        cg_elem.set('name', 'Criteria')
        cg_elem.set('sort_order', '1')

        # Level set (canonical levels in reverse order for display)
        level_set_elem = ET.SubElement(cg_elem, 'level_set')
        levels_elem = ET.SubElement(level_set_elem, 'levels')

        # Canonical levels: Exemplary (3), Good/Satisfactory (2), Developing/Poor (1), Unsatisfactory (0)
        # Display order: sorted by value descending, then by name
        level_definitions = [
            ('Exemplary', 3.0, 60000),
            ('Satisfactory', 2.0, 60001),
            ('Developing', 1.0, 60002),
            ('Unsatisfactory', 0.0, 60003),
        ]

        for i, (level_name, level_value, level_id) in enumerate(level_definitions, 1):
            level_elem = ET.SubElement(levels_elem, 'level')
            level_elem.set('name', level_name)
            level_elem.set('sort_order', str(i))
            level_elem.set('level_id', str(level_id))

        # Criteria
        criteria_elem = ET.SubElement(cg_elem, 'criteria')

        for sort_order, criterion in enumerate(self.rubric.criteria, 1):
            criterion_elem = self._create_criterion_element(criterion, sort_order)
            criteria_elem.append(criterion_elem)

        return cg_elem

    def _create_criterion_element(self, criterion: Criterion, sort_order: int) -> ET.Element:
        """Create <criterion> element with cells for each level."""
        # Include weight in criterion name for visibility
        criterion_name = f"{criterion.name} ({criterion.weight_pct})"

        criterion_elem = ET.Element('criterion')
        criterion_elem.set('name', criterion_name)
        criterion_elem.set('sort_order', str(sort_order))

        # Cells (one per level)
        cells_elem = ET.SubElement(criterion_elem, 'cells')

        # Normalize level names to canonical forms for matching
        canonical_levels = [
            ('Exemplary', 3.0, 60000),
            ('Satisfactory', 2.0, 60001),
            ('Developing', 1.0, 60002),
            ('Unsatisfactory', 0.0, 60003),
        ]

        for canonical_name, canonical_value, level_id in canonical_levels:
            # Find corresponding criterion level
            matching_level = None
            for crit_level in criterion.levels:
                if crit_level.value == canonical_value:
                    matching_level = crit_level
                    break

            # If no match by value, skip
            if not matching_level:
                continue

            cell_elem = self._create_cell_element(matching_level, level_id)
            cells_elem.append(cell_elem)

        return criterion_elem

    def _create_cell_element(self, level: Level, level_id: int) -> ET.Element:
        """Create <cell> element for a criterion level."""
        cell_elem = ET.Element('cell')
        cell_elem.set('level_id', str(level_id))
        cell_elem.set('cell_value', '')

        # Description
        desc_elem = ET.SubElement(cell_elem, 'description')
        desc_elem.set('text_type', 'text/html')

        text_elem = ET.SubElement(desc_elem, 'text')

        # Build description content
        description = level.description

        # Append indicators if available
        if level.indicators:
            description += '\n\nIndicators:\n'
            description += '\n'.join(f'• {ind}' for ind in level.indicators)

        # Convert text to HTML-safe format
        # Escape special characters and convert newlines to <br>
        description_html = self._text_to_html(description)
        text_elem.text = description_html

        # Feedback (empty)
        feedback_elem = ET.SubElement(cell_elem, 'feedback')
        feedback_elem.set('text_type', 'text/html')
        feedback_text = ET.SubElement(feedback_elem, 'text')
        feedback_text.text = ''

        return cell_elem

    def _create_overall_level_set(self) -> ET.Element:
        """Create <overall_level_set> with default score thresholds (0-3 scale)."""
        overall_set_elem = ET.Element('overall_level_set')
        overall_levels_elem = ET.SubElement(overall_set_elem, 'overall_levels')

        # Standard 0-3 scale thresholds
        # Exemplary: 3+, Good: 2-2.9, Developing: 1-1.9, Unsatisfactory: <1
        thresholds = [
            ('Exemplary', 3.0),
            ('Good', 2.0),
            ('Developing', 1.0),
            ('Unsatisfactory', 0.0),
        ]

        for i, (level_name, threshold) in enumerate(thresholds, 1):
            overall_level_elem = ET.SubElement(overall_levels_elem, 'overall_level')
            overall_level_elem.set('name', level_name)
            overall_level_elem.set('sort_order', str(i))

            # Description
            desc_elem = ET.SubElement(overall_level_elem, 'description')
            desc_elem.set('text_type', 'text')
            text_elem = ET.SubElement(desc_elem, 'text')
            text_elem.text = ''

            # Feedback
            feedback_elem = ET.SubElement(overall_level_elem, 'feedback')
            feedback_elem.set('text_type', 'text')
            feedback_text = ET.SubElement(feedback_elem, 'text')
            feedback_text.text = ''

        return overall_set_elem

    def _text_to_html(self, text: str) -> str:
        """Convert plain text to HTML, escaping special characters."""
        # Escape HTML special characters
        text = text.replace('&', '&amp;')
        text = text.replace('<', '&lt;')
        text = text.replace('>', '&gt;')
        text = text.replace('"', '&quot;')

        # Convert newlines to <br> tags
        text = text.replace('\n', '<br/>')

        # Wrap in <p> tags
        return f'<p>{text}</p>'
