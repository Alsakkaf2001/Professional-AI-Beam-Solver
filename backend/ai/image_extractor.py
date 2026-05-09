"""Structural image extraction using LemonFox AI."""
import os
from typing import Dict
from ai.lemonfox_client import LemonFoxClient


class StructuralImageExtractor:
    """Extract FEM structural data from uploaded images using LemonFox."""

    def __init__(self, api_key: str = None):
        self.client = LemonFoxClient(api_key or os.getenv('LEMONFOX_API_KEY'))

    def extract_and_build(self, image_path: str, auto_repair: bool = True) -> Dict:
        """
        Run Gemini vision extraction and optionally repair the result.

        Returns:
            {
                status, original_extraction, repaired_data,
                needs_repair, repairs_made, [repair_error]
            }
        """
        original = self.client.extract_structure_from_image(image_path)

        result = {
            'status':              'success',
            'original_extraction': original,
            'needs_repair':        False,
            'repairs_made':        []
        }

        if auto_repair:
            try:
                repaired               = self.client.repair_structural_data(original)
                result['repaired_data']  = repaired
                result['repairs_made']   = repaired.get('repairs', [])
                result['needs_repair']   = bool(result['repairs_made'])
            except Exception as e:
                result['repair_error'] = str(e)
                result['repaired_data'] = original
        else:
            result['repaired_data'] = original

        return result

    def validate_extraction(self, structure_data: Dict) -> Dict:
        """
        Validate extracted structure (geometry + support + connectivity checks).

        Returns:
            { valid, issues, warnings, stats }
        """
        nodes    = structure_data.get('nodes', [])
        elements = structure_data.get('elements', [])
        supports = structure_data.get('supports', [])
        loads    = structure_data.get('loads', [])

        report = {
            'valid':    True,
            'issues':   [],
            'warnings': [],
            'stats': {
                'nodes':    len(nodes),
                'elements': len(elements),
                'supports': len(supports),
                'loads':    len(loads)
            }
        }

        # ── basic completeness ──────────────────────────────────────────
        if not nodes:
            report['valid'] = False
            report['issues'].append('No nodes extracted')
        if not elements:
            report['valid'] = False
            report['issues'].append('No elements extracted')
        if not supports:
            report['warnings'].append('No supports detected — structure may be unstable')

        # ── node ID uniqueness ──────────────────────────────────────────
        node_ids = [n['id'] for n in nodes]
        if len(node_ids) != len(set(node_ids)):
            report['issues'].append('Duplicate node IDs found')

        # ── element connectivity ────────────────────────────────────────
        node_id_set = {n['id'] for n in nodes}
        for el in elements:
            ni = el.get('node_i') or el.get('n1')
            nj = el.get('node_j') or el.get('n2')
            if ni not in node_id_set or nj not in node_id_set:
                report['valid'] = False
                report['issues'].append(f"Element {el.get('id','?')}: invalid node reference ({ni}, {nj})")

        # ── support DOF count ───────────────────────────────────────────
        dof_map  = {'fixed': 3, 'pin': 2, 'roller_x': 1, 'roller_y': 1}
        total_dof = sum(dof_map.get(s.get('type', s.get('support_type', '')), 1) for s in supports)
        if supports and total_dof < 3:
            report['valid'] = False
            report['issues'].append(
                f'Insufficient constraints: {total_dof} DOF (need ≥ 3 for 2-D stability)'
            )

        # ── zero-length elements ────────────────────────────────────────
        node_xy = {n['id']: (n['x'], n['y']) for n in nodes}
        for el in elements:
            ni = el.get('node_i') or el.get('n1')
            nj = el.get('node_j') or el.get('n2')
            if ni in node_xy and nj in node_xy:
                xi, yi = node_xy[ni]
                xj, yj = node_xy[nj]
                length = ((xi - xj) ** 2 + (yi - yj) ** 2) ** 0.5
                if length < 0.01:
                    report['valid'] = False
                    report['issues'].append(f"Element {el.get('id','?')}: zero-length member")

        if report['issues']:
            report['valid'] = False

        return report
