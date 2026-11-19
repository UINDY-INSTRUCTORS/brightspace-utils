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

    # Level names normalised to Brightspace's usual scale. Any other name (e.g. "Met",
    # "Not yet") is kept as written.
    CANONICAL = {'excellent': 'Exemplary', 'exemplary': 'Exemplary', 'good': 'Satisfactory',
                 'satisfactory': 'Satisfactory', 'poor': 'Developing', 'developing': 'Developing',
                 'unsatisfactory': 'Unsatisfactory'}
    FULL_SCALE = [('Exemplary', 3.0), ('Satisfactory', 2.0), ('Developing', 1.0), ('Unsatisfactory', 0.0)]

    def _assign_level_ids(self):
        """
        The rubric's level set, highest first, as [(name, value, level_id)].

        A rubric whose levels are all on the usual E/S/D/U scale gets the full four-level
        set, as before, even if some levels are unused. A rubric with any other level name
        (a two-level Met / Not yet rubric) gets exactly the levels it uses, named as written.
        """
        present = {}
        for criterion in self.rubric.criteria:
            for level in criterion.levels:
                present.setdefault(level.value, level.name)
        if all(n.lower() in self.CANONICAL for n in present.values()):
            levels = self.FULL_SCALE
        else:
            levels = [(self.CANONICAL.get(n.lower(), n), v)
                      for v, n in sorted(present.items(), reverse=True)]
        self.level_set = [(name, value, 60000 + i) for i, (name, value) in enumerate(levels)]
        self.level_ids = {value: level_id for _, value, level_id in self.level_set}

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

        for i, (level_name, level_value, level_id) in enumerate(self.level_set, 1):
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

        for _, level_value, level_id in self.level_set:
            matching_level = next((l for l in criterion.levels if l.value == level_value), None)
            if matching_level:
                cells_elem.append(self._create_cell_element(matching_level, level_id))

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
        if self.level_set != [(n, v, 60000 + i) for i, (n, v) in enumerate(self.FULL_SCALE)]:
            thresholds = [(name, value) for name, value, _ in self.level_set]

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
