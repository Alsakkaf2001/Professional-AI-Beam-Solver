"""AI-assisted structural data repair using LemonFox."""
import os
from typing import Dict
from ai.lemonfox_client import LemonFoxClient


class StructuralRepair:
    """Repair and validate extracted structural data with LemonFox."""

    def __init__(self, api_key: str = None):
        self.client = LemonFoxClient(api_key or os.getenv('LEMONFOX_API_KEY'))

    def repair(self, structure_data: Dict) -> Dict:
        return self.client.repair_structural_data(structure_data)

    def normalize_coordinates(self, structure_data: Dict,
                               target_max: float = 100.0) -> Dict:
        """Normalise node x/y coordinates to [0, target_max] range."""
        nodes = structure_data.get('nodes', [])
        if not nodes:
            return structure_data

        xs = [n['x'] for n in nodes]
        ys = [n['y'] for n in nodes]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        span = max(max_x - min_x, max_y - min_y, 1e-9)

        for n in nodes:
            n['x'] = round((n['x'] - min_x) / span * target_max, 4)
            n['y'] = round((n['y'] - min_y) / span * target_max, 4)

        return structure_data
