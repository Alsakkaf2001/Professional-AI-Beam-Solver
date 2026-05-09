"""Post-processing and results recovery."""
import numpy as np
from typing import List, Dict, Tuple
from .nodes import Node
from .elements import BeamElement2D
from .loads import PointLoad, DistributedLoad


class ResultsRecovery:
    """Extract and compute results from solved structure."""
    
    def __init__(self, nodes: List[Node], elements: List[BeamElement2D],
                 loads: List[PointLoad] = None):
        """Initialize results recovery."""
        self.nodes = nodes
        self.elements = elements
        self.loads = loads or []
    
    def get_displacements(self) -> List[Dict]:
        """Get node displacements."""
        displacements = []
        for node in self.nodes:
            displacements.append({
                'node_id': node.id,
                'ux': node.ux,
                'uy': node.uy,
                'rz': np.degrees(node.rz) if abs(node.rz) < 0.1 else node.rz,  # Convert to degrees if small
                'magnitude': np.sqrt(node.ux**2 + node.uy**2)
            })
        return displacements
    
    def get_reactions(self) -> List[Dict]:
        """Get support reactions."""
        reactions = []
        for node in self.nodes:
            if node.constrained_ux or node.constrained_uy or node.constrained_rz:
                reactions.append({
                    'node_id': node.id,
                    'fx': node.fx,
                    'fy': node.fy,
                    'mz': node.mz,
                    'x': node.x,
                    'y': node.y
                })
        return reactions
    
    def compute_element_forces(self, elem: BeamElement2D) -> Dict:
        """
        Compute internal forces for a beam element.
        
        Returns local forces at element ends.
        """
        # Get node displacements in global coordinates
        u_i = np.array([elem.node_i.ux, elem.node_i.uy, elem.node_i.rz])
        u_j = np.array([elem.node_j.ux, elem.node_j.uy, elem.node_j.rz])
        u_elem_global = np.concatenate([u_i, u_j])
        
        # Transform to local coordinates
        T = elem.get_transformation_matrix()
        u_elem_local = T @ u_elem_global
        
        # Local member stiffness
        f_elem_local = elem.k_local @ u_elem_local
        
        # Extract member forces
        # Local DOF: [u_x_i, u_y_i, r_z_i, u_x_j, u_y_j, r_z_j]
        forces = {
            'N_i': f_elem_local[0],      # Axial force at i
            'V_i': f_elem_local[1],      # Shear at i (local y)
            'M_i': f_elem_local[2],      # Moment at i
            'N_j': f_elem_local[3],      # Axial force at j
            'V_j': f_elem_local[4],      # Shear at j
            'M_j': f_elem_local[5]       # Moment at j
        }
        
        return forces
    
    def compute_sfd_bmd(self, elem: BeamElement2D, n_points: int = 20) -> Tuple[List[float], List[float], List[float]]:
        """
        Compute shear force and bending moment diagrams for an element.
        
        Args:
            elem: Beam element
            n_points: Number of points along element
        
        Returns:
            (x_coords, shear_forces, bending_moments)
        """
        forces = self.compute_element_forces(elem)
        
        # Initial values at element start
        V_i = forces['V_i']
        M_i = forces['M_i']
        N_i = forces['N_i']
        
        # Note: Without distributed loads in element, V and M are linear
        # With distributed loads, they would be quadratic/cubic
        
        x_coords = np.linspace(0, elem.L, n_points)
        shear_forces = []
        bending_moments = []
        
        # Linear interpolation for constant element (no loads on element)
        for x in x_coords:
            # Shear is constant along element
            V = V_i
            shear_forces.append(V)
            
            # Moment varies linearly: M(x) = M_i + V_i * x
            M = M_i + V_i * x
            bending_moments.append(M)
        
        return x_coords.tolist(), shear_forces, bending_moments
    
    def compute_deformation_profile(self, elem: BeamElement2D, n_points: int = 20) -> Tuple[List[float], List[float]]:
        """
        Compute deformed shape of element using Hermite interpolation.
        
        Args:
            elem: Beam element
            n_points: Number of points
        
        Returns:
            (x_local, y_deformed)
        """
        # Element's nodal displacements (transverse only)
        # In local coordinates
        u_i = np.array([elem.node_i.ux, elem.node_i.uy, elem.node_i.rz])
        u_j = np.array([elem.node_j.ux, elem.node_j.uy, elem.node_j.rz])
        u_elem_global = np.concatenate([u_i, u_j])
        
        T = elem.get_transformation_matrix()
        u_elem_local = T @ u_elem_global
        
        # Local transverse components [v_i, theta_i, v_j, theta_j]
        v_i = u_elem_local[1]
        theta_i = u_elem_local[2]
        v_j = u_elem_local[4]
        theta_j = u_elem_local[5]
        
        L = elem.L
        x_local = np.linspace(0, L, n_points)
        y_deformed = []
        
        # Cubic Hermite interpolation
        for x in x_local:
            xi = x / L  # Normalized coordinate [0, 1]
            
            # Hermite basis functions
            N1 = 1 - 3*xi**2 + 2*xi**3
            N2 = xi*(1 - 2*xi + xi**2) * L
            N3 = 3*xi**2 - 2*xi**3
            N4 = xi*(xi**2 - xi) * L
            
            # Interpolated deflection
            v = N1*v_i + N2*theta_i + N3*v_j + N4*theta_j
            y_deformed.append(v)
        
        return x_local.tolist(), y_deformed
    
    def compute_global_diagrams(self) -> Dict:
        """
        Compute SFD and BMD diagrams for entire structure.
        
        Returns:
            Dictionary with diagram data for each element
        """
        diagrams = {}
        
        for elem in self.elements:
            elem_key = f"elem_{elem.id}"
            
            x_local, sfd, bmd = self.compute_sfd_bmd(elem)
            
            # Transform x_local to global coordinates
            dx = elem.node_j.x - elem.node_i.x
            dy = elem.node_j.y - elem.node_i.y
            
            x_global = [elem.node_i.x + x_local[i] * dx / elem.L for i in range(len(x_local))]
            y_global = [elem.node_i.y + x_local[i] * dy / elem.L for i in range(len(x_local))]
            
            diagrams[elem_key] = {
                'element_id': elem.id,
                'node_i': elem.node_i.id,
                'node_j': elem.node_j.id,
                'x_global': x_global,
                'y_global': y_global,
                'shear_forces': sfd,
                'bending_moments': bmd
            }
        
        return diagrams
