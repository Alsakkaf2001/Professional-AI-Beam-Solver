"""Loads and load cases."""
from enum import Enum
from typing import Dict, List
import numpy as np
from .nodes import Node


class LoadType(Enum):
    """Types of loads."""
    POINT = 'point'
    DISTRIBUTED = 'distributed'
    MOMENT = 'moment'


class PointLoad:
    """Point load at a node."""
    
    _load_id_counter = 0
    
    def __init__(self, node: Node, fx: float = 0.0, fy: float = 0.0, mz: float = 0.0, load_id: int = None):
        """
        Initialize point load.
        
        Args:
            node: Node with load
            fx: Horizontal force (kN)
            fy: Vertical force (kN)
            mz: Moment (kN·m)
            load_id: Optional load ID
        """
        if load_id is None:
            PointLoad._load_id_counter += 1
            self.id = PointLoad._load_id_counter
        else:
            self.id = load_id
            PointLoad._load_id_counter = max(PointLoad._load_id_counter, load_id)
        
        self.node = node
        self.fx = float(fx)  # kN
        self.fy = float(fy)  # kN
        self.mz = float(mz)  # kN·m
    
    def magnitude(self) -> float:
        """Get load magnitude."""
        return np.sqrt(self.fx**2 + self.fy**2)
    
    def to_dict(self) -> Dict:
        """Serialize to dictionary."""
        return {
            'id': self.id,
            'type': 'point',
            'node_id': self.node.id,
            'fx': self.fx,
            'fy': self.fy,
            'mz': self.mz
        }
    
    @classmethod
    def from_dict(cls, data: Dict, node: Node) -> 'PointLoad':
        """Deserialize from dictionary."""
        return cls(node, data['fx'], data['fy'], data.get('mz', 0.0), data.get('id'))
    
    def __repr__(self) -> str:
        return f"PointLoad(id={self.id}, node={self.node.id}, fx={self.fx}kN, fy={self.fy}kN, mz={self.mz}kN·m)"


class DistributedLoad:
    """Distributed load on a beam element."""
    
    _load_id_counter = 0
    
    def __init__(
        self,
        element_id: int,
        q_start: float,
        q_end: float = None,
        load_id: int = None,
        direction: str = 'y'
    ):
        """
        Initialize distributed load (UDL).
        
        Args:
            element_id: Element ID where load is applied
            q_start: Load intensity at start (kN/m)
            q_end: Load intensity at end (kN/m), if None = q_start (uniform)
            load_id: Optional load ID
            direction: 'x' for axial, 'y' for transverse
        """
        if load_id is None:
            DistributedLoad._load_id_counter += 1
            self.id = DistributedLoad._load_id_counter
        else:
            self.id = load_id
            DistributedLoad._load_id_counter = max(DistributedLoad._load_id_counter, load_id)
        
        self.element_id = element_id
        self.q_start = float(q_start)  # kN/m
        self.q_end = float(q_end) if q_end is not None else self.q_start
        self.direction = direction
        self.is_uniform = abs(self.q_start - self.q_end) < 1e-10
    
    def to_dict(self) -> Dict:
        """Serialize to dictionary."""
        return {
            'id': self.id,
            'type': 'distributed',
            'element_id': self.element_id,
            'q_start': self.q_start,
            'q_end': self.q_end,
            'direction': self.direction,
            'is_uniform': self.is_uniform
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'DistributedLoad':
        """Deserialize from dictionary."""
        return cls(
            data['element_id'],
            data['q_start'],
            data.get('q_end'),
            data.get('id'),
            data.get('direction', 'y')
        )
    
    def __repr__(self) -> str:
        if self.is_uniform:
            return f"DistributedLoad(id={self.id}, element={self.element_id}, q={self.q_start}kN/m, dir={self.direction})"
        else:
            return f"DistributedLoad(id={self.id}, element={self.element_id}, q={self.q_start}-{self.q_end}kN/m, dir={self.direction})"
