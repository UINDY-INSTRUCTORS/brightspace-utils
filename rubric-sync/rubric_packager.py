"""Package rubric as importable Brightspace ZIP file."""

import zipfile
from io import StringIO
from pathlib import Path
from rubric_data import RubricData
from rubric_to_d2l import RubricToD2L


class RubricPackager:
    """Create importable Brightspace package (ZIP with imsmanifest.xml + rubrics_d2l.xml)."""

    def __init__(self, rubric_data: RubricData, use_scoring: bool = True):
        self.rubric = rubric_data
        self.use_scoring = use_scoring

    def create_package(self, output_path: Path) -> Path:
        """
        Create importable Brightspace ZIP package.

        Args:
            output_path: Where to save the .zip file

        Returns:
            Path to created ZIP file
        """
        output_path = Path(output_path)

        # Generate rubrics XML
        converter = RubricToD2L(
            self.rubric,
            use_scoring=self.use_scoring
        )
        rubrics_xml = converter.generate_xml()

        # Generate manifest XML
        manifest_xml = self._generate_manifest()

        # Create ZIP
        with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            zf.writestr('imsmanifest.xml', manifest_xml)
            zf.writestr('rubrics_d2l.xml', rubrics_xml)

        return output_path

    def _generate_manifest(self) -> str:
        """Generate imsmanifest.xml for the package."""
        # Use a hardcoded but valid manifest structure
        # The manifest just references the rubrics_d2l.xml file
        manifest = '''<?xml version="1.0" encoding="UTF-8"?>
<manifest identifier="D2L_Rubric" xmlns:d2l_2p0="http://desire2learn.com/xsd/d2lcp_v2p0" xmlns:scorm_1p2="http://www.adlnet.org/xsd/adlcp_rootv1p2" xmlns:imsmd="http://www.imsglobal.org/xsd/imsmd_rootv1p2p1" xmlns="http://www.imsglobal.org/xsd/imscp_v1p1">
    <metadata>
        <imsmd:lom>
            <imsmd:general>
                <imsmd:title>
                    <imsmd:langstring xml:lang="en-us">''' + self.rubric.title + '''</imsmd:langstring>
                </imsmd:title>
                <imsmd:language>en-us</imsmd:language>
            </imsmd:general>
        </imsmd:lom>
    </metadata>
    <resources>
        <resource identifier="res_rubrics" type="webcontent" d2l_2p0:material_type="d2lrubrics" d2l_2p0:link_target="" href="rubrics_d2l.xml" title=""/>
    </resources>
</manifest>'''
        return manifest
