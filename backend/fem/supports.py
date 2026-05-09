"""Support and boundary conditions."""
from enum import Enum
from typing import Dict
from .nodes import Node


class SupportType(Enum):
    """Support types in 2D structural analysis."""
    PIN = 'pin'  # Supported in UX, UY; free RZ
    FIXED = 'fixed'  # Supported in UX, UY, RZ
    ROLLER_X = 'roller_x'  # Supported in UY only (horizontal roller)
    ROLLER_Y = 'roller_y'  # Supported in UX only (vertical roller)
    SPRING = 'spring'  # Elastic support


class Support:
    """Represents a support/boundary condition at a node."""
    
    _support_id_counter = 0
    
    def __init__(self, node: Node, support_type: SupportType, sup_id: int = None):
        """
        Initialize support.
        
        Args:
            node: Node with support
            support_type: Type of support
            sup_id: Optional support ID
        """
        if sup_id is None:
            Support._support_id_counter += 1
            self.id = Support._support_id_counter
        else:
            self.id = sup_id
            Support._support_id_counter = max(Support._support_id_counter, sup_id)
        
        self.node = node
        self.type = support_type
        
        # Apply constraints based on support type
        self._apply_constraints()
    
    def _apply_constraints(self):
        """Apply DOF constraints to node based on support type."""
        if self.type == SupportType.PIN:
            self.node.constrained_ux = True
            self.node.constrained_uy = True
            self.node.constrained_rz = False
        elif self.type == SupportType.FIXED:
            self.node.constrained_ux = True
            self.node.constrained_uy = True
            self.node.constrained_rz = True
        elif self.type == SupportType.ROLLER_X:
            self.node.constrained_ux = False
            self.node.constrained_uy = True
            self.node.constrained_rz = False
        elif self.type == SupportType.ROLLER_Y:
            self.node.constrained_ux = True
            self.node.constrained_uy = False
            self.node.constrained_rz = False
    
    def to_dict(self) -> Dict:
        """Serialize to dictionary."""
        return {
            'id': self.id,
            'node_id': self.node.id,
            'type': self.type.value
        }
    
    @classmethod
    def from_dict(cls, data: Dict, node: Node) -> 'Support':
        """Deserialize from dictionary."""
        sup_type = SupportType(data['type'])
        return cls(node, sup_type, data.get('id'))
    
    def __repr__(self) -> str:
        return f"Support(id={self.id}, node={self.node.id}, type={self.type.value})"
