"""2D Beam element implementation using Euler-Bernoulli theory."""
import numpy as np
from typing import Dict, Tuple
from .nodes import Node
from .materials import Material
from .sections import CrossSection


class BeamElement2D:
    """
    2D Euler-Bernoulli beam element with 6 DOF (3 per node).
    
    Local coordinate system: x-axis along beam
    Global coordinate system: X-Y plane
    """
    
    _element_id_counter = 0
    
    def __init__(
        self,
        node_i: Node,
        node_j: Node,
        material: Material,
        section: CrossSection,
        element_id: int = None
    ):
        """
        Initialize 2D beam element.
        
        Args:
            node_i: Start node
            node_j: End node
            material: Material properties
            section: Cross-sectional properties
            element_id: Optional element ID
        """
        if element_id is None:
            BeamElement2D._element_id_counter += 1
            self.id = BeamElement2D._element_id_counter
        else:
            self.id = element_id
            BeamElement2D._element_id_counter = max(BeamElement2D._element_id_counter, element_id)
        
        self.node_i = node_i
        self.node_j = node_j
        self.material = material
        self.section = section
        
        # Calculate length
        self.L = node_i.distance_to(node_j)
        if self.L < 1e-6:
            raise ValueError(f"Element {self.id}: zero-length member between nodes {node_i.id} and {node_j.id}")
        
        # Calculate angle (rotation from X-axis to beam)
        dx = node_j.x - node_i.x
        dy = node_j.y - node_i.y
        self.cos_theta = dx / self.L
        self.sin_theta = dy / self.L
        
        # Shear area (for shear deformation, if needed)
        self.As = self.section.A  # Approximate
        
        # Local stiffness matrix components
        self._compute_local_stiffness()
    
    def _compute_local_stiffness(self):
        """Compute local stiffness matrix for 2D beam element."""
        E = self.material.E  # MPa
        A = self.section.A  # mm²
        I = self.section.I  # mm⁴
        L = self.L  # mm
        
        # Stiffness coefficients (Euler-Bernoulli theory)
        EA_L = E * A / L
        EI_L3 = E * I / (L**3)
        EI_L2 = E * I / (L**2)
        EI_L = E * I / L
        
        # Local stiffness matrix (6x6) - nodes i,j with DOF [ux, uy, rz]
        self.k_local = np.zeros((6, 6))
        
        # Axial stiffness
        self.k_local[0, 0] = EA_L
        self.k_local[0, 3] = -EA_L
        self.k_local[3, 0] = -EA_L
        self.k_local[3, 3] = EA_L
        
        # Transverse and bending stiffness
        self.k_local[1, 1] = 12 * EI_L3
        self.k_local[1, 2] = 6 * EI_L2
        self.k_local[1, 4] = -12 * EI_L3
        self.k_local[1, 5] = 6 * EI_L2
        
        self.k_local[2, 1] = 6 * EI_L2
        self.k_local[2, 2] = 4 * EI_L
        self.k_local[2, 4] = -6 * EI_L2
        self.k_local[2, 5] = 2 * EI_L
        
        self.k_local[4, 1] = -12 * EI_L3
        self.k_local[4, 2] = -6 * EI_L2
        self.k_local[4, 4] = 12 * EI_L3
        self.k_local[4, 5] = -6 * EI_L2
        
        self.k_local[5, 1] = 6 * EI_L2
        self.k_local[5, 2] = 2 * EI_L
        self.k_local[5, 4] = -6 * EI_L2
        self.k_local[5, 5] = 4 * EI_L
    
    def get_transformation_matrix(self) -> np.ndarray:
        """
        Get transformation matrix from local to global coordinates.
        
        Returns:
            6x6 transformation matrix T
        """
        c = self.cos_theta
        s = self.sin_theta
        
        # Transformation block for rotation
        R = np.array([
            [c, s, 0],
            [-s, c, 0],
            [0, 0, 1]
        ])
        
        # Full transformation matrix for 6 DOF
        T = np.zeros((6, 6))
        T[0:3, 0:3] = R
        T[3:6, 3:6] = R
        
        return T
    
    def get_global_stiffness(self) -> np.ndarray:
        """
        Get global stiffness matrix.
        
        Returns:
            6x6 global stiffness matrix
        """
        T = self.get_transformation_matrix()
        return T.T @ self.k_local @ T
    
    def to_dict(self) -> Dict:
        """Serialize element to dictionary."""
        return {
            'id': self.id,
            'node_i': self.node_i.id,
            'node_j': self.node_j.id,
            'material': self.material.to_dict(),
            'section': self.section.to_dict(),
            'length': self.L,
            'angle': np.degrees(np.arctan2(self.sin_theta, self.cos_theta))
        }
    
    def __repr__(self) -> str:
        return f"BeamElement2D(id={self.id}, nodes={self.node_i.id}-{self.node_j.id}, L={self.L:.2f}mm)"
