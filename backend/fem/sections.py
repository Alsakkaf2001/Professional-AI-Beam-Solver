"""Cross-sectional properties for beam elements."""
from typing import Dict
import math


class CrossSection:
    """Represents beam cross-sectional properties."""
    
    # Standard sections database — I values in mm⁴ (= cm⁴ × 10000)
    STANDARD_SECTIONS = {
        'IPE-100': {'A': 1032,  'I': 1710000,   'h': 100, 'b': 55},
        'IPE-200': {'A': 2850,  'I': 19430000,  'h': 200, 'b': 100},
        'IPE-300': {'A': 5380,  'I': 83600000,  'h': 300, 'b': 150},
        'HEB-100': {'A': 2600,  'I': 4495000,   'h': 100, 'b': 100},
        'HEB-200': {'A': 6100,  'I': 56960000,  'h': 200, 'b': 200},
        'pipe-50x3': {'A': 471, 'I': 122800,    'd': 50,  't': 3},
    }
    
    def __init__(self, name: str, area: float, inertia: float, sec_id: int = None):
        """
        Initialize cross-section.
        
        Args:
            name: Section name
            area: Cross-sectional area (mm²)
            inertia: Second moment of inertia (mm⁴)
            sec_id: Optional section ID
        """
        self.id = sec_id or id(self)
        self.name = name
        self.A = float(area)  # mm²
        self.I = float(inertia)  # mm⁴
    
    def to_dict(self) -> Dict:
        """Serialize to dictionary."""
        return {
            'id': self.id,
            'name': self.name,
            'A': self.A,
            'I': self.I
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'CrossSection':
        """Deserialize from dictionary."""
        return cls(data['name'], data['A'], data['I'], data.get('id'))
    
    @classmethod
    def rectangle(cls, width: float, height: float) -> 'CrossSection':
        """Create rectangular cross-section."""
        A = width * height
        I = (width * height**3) / 12
        return cls(f'Rectangle {width}x{height}mm', A, I)
    
    @classmethod
    def circle(cls, diameter: float) -> 'CrossSection':
        """Create circular cross-section."""
        r = diameter / 2
        A = math.pi * r**2
        I = math.pi * (diameter**4) / 64
        return cls(f'Circle d={diameter}mm', A, I)
    
    @classmethod
    def ipe(cls, size: str) -> 'CrossSection':
        """Create standard IPE section."""
        if size not in cls.STANDARD_SECTIONS:
            raise ValueError(f"Unknown IPE size: {size}")
        sec = cls.STANDARD_SECTIONS[size]
        return cls(size, sec['A'], sec['I'])
    
    @classmethod
    def heb(cls, size: str) -> 'CrossSection':
        """Create standard HEB section."""
        if size not in cls.STANDARD_SECTIONS:
            raise ValueError(f"Unknown HEB size: {size}")
        sec = cls.STANDARD_SECTIONS[size]
        return cls(size, sec['A'], sec['I'])
    
    def __repr__(self) -> str:
        return f"Section({self.name}, A={self.A}mm², I={self.I}mm⁴)"
