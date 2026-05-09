"""Material properties for structural elements."""
from typing import Dict


class Material:
    """Represents material properties (steel, concrete, etc.)."""
    
    # Standard materials database
    STANDARD_MATERIALS = {
        'steel': {'E': 200000, 'name': 'Steel', 'density': 7850},
        'aluminum': {'E': 70000, 'name': 'Aluminum', 'density': 2700},
        'concrete': {'E': 30000, 'name': 'Concrete (C30)', 'density': 2400},
    }
    
    def __init__(self, name: str, young_modulus: float, mat_id: int = None):
        """
        Initialize material.
        
        Args:
            name: Material name
            young_modulus: Young's modulus (MPa)
            mat_id: Optional material ID
        """
        self.id = mat_id or id(self)
        self.name = name
        self.E = float(young_modulus)  # MPa
    
    def to_dict(self) -> Dict:
        """Serialize to dictionary."""
        return {
            'id': self.id,
            'name': self.name,
            'E': self.E
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'Material':
        """Deserialize from dictionary."""
        return cls(data['name'], data['E'], data.get('id'))
    
    @classmethod
    def steel(cls) -> 'Material':
        """Create standard steel material (E=200 GPa)."""
        return cls('Steel', 200000)
    
    @classmethod
    def aluminum(cls) -> 'Material':
        """Create standard aluminum material (E=70 GPa)."""
        return cls('Aluminum', 70000)
    
    @classmethod
    def concrete(cls) -> 'Material':
        """Create standard concrete material (E=30 GPa)."""
        return cls('Concrete (C30)', 30000)
    
    def __repr__(self) -> str:
        return f"Material({self.name}, E={self.E} MPa)"
