"""Node representation and management."""
import numpy as np
from typing import List, Dict


class Node:
    """Represents a node in the structure with 3 DOFs: UX, UY, RZ."""
    
    # Class variable for auto-ID
    _node_id_counter = 0
    
    def __init__(self, x: float, y: float, node_id: int = None):
        """
        Initialize a node.
        
        Args:
            x: X coordinate (mm)
            y: Y coordinate (mm)
            node_id: Optional node ID (auto-assigned if None)
        """
        if node_id is None:
            Node._node_id_counter += 1
            self.id = Node._node_id_counter
        else:
            self.id = node_id
            Node._node_id_counter = max(Node._node_id_counter, node_id)
        
        self.x = float(x)
        self.y = float(y)
        
        # Displacements (initialized as zero)
        self.ux = 0.0  # Horizontal displacement
        self.uy = 0.0  # Vertical displacement
        self.rz = 0.0  # Rotation
        
        # Forces/reactions (computed during solving)
        self.fx = 0.0  # Horizontal reaction
        self.fy = 0.0  # Vertical reaction
        self.mz = 0.0  # Moment reaction
        
        # Constraints (DOF constraint flags)
        self.constrained_ux = False
        self.constrained_uy = False
        self.constrained_rz = False
    
    def to_dict(self) -> Dict:
        """Serialize node to dictionary."""
        return {
            'id': self.id,
            'x': self.x,
            'y': self.y,
            'ux': self.ux,
            'uy': self.uy,
            'rz': self.rz,
            'fx': self.fx,
            'fy': self.fy,
            'mz': self.mz,
            'constrained_ux': self.constrained_ux,
            'constrained_uy': self.constrained_uy,
            'constrained_rz': self.constrained_rz
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'Node':
        """Deserialize node from dictionary."""
        node = cls(data['x'], data['y'], data['id'])
        node.ux = data.get('ux', 0.0)
        node.uy = data.get('uy', 0.0)
        node.rz = data.get('rz', 0.0)
        node.fx = data.get('fx', 0.0)
        node.fy = data.get('fy', 0.0)
        node.mz = data.get('mz', 0.0)
        node.constrained_ux = data.get('constrained_ux', False)
        node.constrained_uy = data.get('constrained_uy', False)
        node.constrained_rz = data.get('constrained_rz', False)
        return node
    
    def distance_to(self, other: 'Node') -> float:
        """Calculate distance to another node."""
        return np.sqrt((self.x - other.x)**2 + (self.y - other.y)**2)
    
    def __repr__(self) -> str:
        return f"Node(id={self.id}, x={self.x:.2f}mm, y={self.y:.2f}mm)"
