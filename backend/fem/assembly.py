"""Global assembly of FEM matrices."""
import numpy as np
from typing import List, Dict, Tuple
from .nodes import Node
from .elements import BeamElement2D
from .supports import Support
from .loads import PointLoad, DistributedLoad


class GlobalAssembly:
    """Assembles global stiffness matrix and load vector."""
    
    def __init__(self, nodes: List[Node], elements: List[BeamElement2D],
                 supports: List[Support], loads: List[PointLoad] = None,
                 distributed_loads: List[DistributedLoad] = None):
        """Initialize assembly."""
        self.nodes = nodes
        self.elements = elements
        self.supports = supports
        self.loads = loads or []
        self.distributed_loads = distributed_loads or []
        
        # Create node ID to index mapping
        self.node_id_to_idx = {node.id: i for i, node in enumerate(nodes)}
        self.element_id_to_obj = {elem.id: elem for elem in elements}
        
        # Total DOF = 3 per node (UX, UY, RZ)
        self.n_dof = len(nodes) * 3
        
        # Global matrices
        self.K_global = np.zeros((self.n_dof, self.n_dof))
        self.F_global = np.zeros(self.n_dof)
        self.F_distributed = np.zeros(self.n_dof)
        
        # DOF mapping: node_i -> DOF indices [ux_idx, uy_idx, rz_idx]
        self._create_dof_mapping()
    
    def _create_dof_mapping(self):
        """Create mapping from node to global DOF indices."""
        self.dof_map = {}  # node_id -> [ux_idx, uy_idx, rz_idx]
        for node_id, node_idx in self.node_id_to_idx.items():
            ux_idx = node_idx * 3
            uy_idx = node_idx * 3 + 1
            rz_idx = node_idx * 3 + 2
            self.dof_map[node_id] = [ux_idx, uy_idx, rz_idx]
    
    def assemble_global_stiffness(self):
        """Assemble global stiffness matrix from elements."""
        self.K_global = np.zeros((self.n_dof, self.n_dof))
        
        for elem in self.elements:
            # Get global stiffness
            K_global_elem = elem.get_global_stiffness()
            
            # Get DOF indices
            i_dof = self.dof_map[elem.node_i.id]
            j_dof = self.dof_map[elem.node_j.id]
            all_dof = i_dof + j_dof
            
            # Add to global stiffness
            for local_i, global_i in enumerate(all_dof):
                for local_j, global_j in enumerate(all_dof):
                    self.K_global[global_i, global_j] += K_global_elem[local_i, local_j]
    
    def assemble_load_vector(self):
        """Assemble global load vector from point loads."""
        self.F_global = np.zeros(self.n_dof)
        
        # Point loads — stiffness matrix is in N and N·mm, so convert kN→N and kN·m→N·mm
        for load in self.loads:
            dof = self.dof_map[load.node.id]
            self.F_global[dof[0]] += load.fx * 1000    # kN → N
            self.F_global[dof[1]] += load.fy * 1000    # kN → N
            self.F_global[dof[2]] += load.mz * 1.0e6   # kN·m → N·mm
        
        # Distributed loads - convert to equivalent point loads at nodes
        self._assemble_distributed_loads()
    
    def _assemble_distributed_loads(self):
        """Convert distributed loads to equivalent point loads."""
        self.F_distributed = np.zeros(self.n_dof)
        
        for d_load in self.distributed_loads:
            if d_load.element_id not in self.element_id_to_obj:
                continue
            
            elem = self.element_id_to_obj[d_load.element_id]
            L = elem.L
            
            # Equivalent nodal forces for distributed load
            # For uniform load q in y-direction on element:
            # F_i = q*L/2, M_i = q*L^2/12, F_j = q*L/2, M_j = -q*L^2/12
            
            q_avg = (d_load.q_start + d_load.q_end) / 2
            
            # Simple integration for trapezoid load
            f_end = q_avg * L / 2
            m_end = q_avg * L * L / 12
            
            i_dof = self.dof_map[elem.node_i.id]
            j_dof = self.dof_map[elem.node_j.id]
            
            if d_load.direction == 'y':
                # Transverse load
                # Element local Y direction transforms to global
                fy_i = f_end * elem.cos_theta  # Global X component (approximate)
                fy_j = f_end * elem.cos_theta
                
                # More accurate: project to global Y
                fy_global_i = f_end  # Simplified
                fy_global_j = f_end
                
                self.F_distributed[i_dof[1]] += fy_global_i
                self.F_distributed[i_dof[2]] += m_end
                self.F_distributed[j_dof[1]] += fy_global_j
                self.F_distributed[j_dof[2]] -= m_end
            
            elif d_load.direction == 'x':
                # Axial load
                fx_i = f_end
                fx_j = f_end
                self.F_distributed[i_dof[0]] += fx_i
                self.F_distributed[j_dof[0]] += fx_j
        
        self.F_global += self.F_distributed
    
    def apply_supports_to_stiffness(self):
        """Apply boundary conditions by modifying K and F."""
        # Find constrained DOF indices
        constrained_dof = []
        for support in self.supports:
            dof = self.dof_map[support.node.id]
            if support.node.constrained_ux:
                constrained_dof.append(dof[0])
            if support.node.constrained_uy:
                constrained_dof.append(dof[1])
            if support.node.constrained_rz:
                constrained_dof.append(dof[2])
        
        # Create constraint matrix (partition method)
        # K_modified = K with constrained rows/columns set appropriately
        self.constrained_dof = sorted(set(constrained_dof))
        self.free_dof = [i for i in range(self.n_dof) if i not in self.constrained_dof]
        
        return self.constrained_dof, self.free_dof
    
    def solve(self) -> Tuple[np.ndarray, Dict]:
        """
        Solve the system K*u = F using boundary conditions.
        
        Returns:
            (displacements, results_dict)
        """
        # Assemble matrices
        self.assemble_global_stiffness()
        self.assemble_load_vector()
        self.apply_supports_to_stiffness()
        
        # Check singularity
        if not self._check_stiffness_matrix():
            raise ValueError("Singular or near-singular stiffness matrix")
        
        # Partition method: solve only for free DOF
        K_ff = self.K_global[np.ix_(self.free_dof, self.free_dof)]
        F_f = self.F_global[self.free_dof]
        
        # Solve
        try:
            u_free = np.linalg.solve(K_ff, F_f)
        except np.linalg.LinAlgError as e:
            raise ValueError(f"Failed to solve system: {e}")
        
        # Reconstruct full displacement vector
        u_global = np.zeros(self.n_dof)
        for i, dof_idx in enumerate(self.free_dof):
            u_global[dof_idx] = u_free[i]
        
        # Update node displacements
        for node in self.nodes:
            idx = self.node_id_to_idx[node.id]
            dof = self.dof_map[node.id]
            node.ux = u_global[dof[0]]
            node.uy = u_global[dof[1]]
            node.rz = u_global[dof[2]]
        
        # Calculate reactions
        reactions = self._calculate_reactions(u_global)
        
        return u_global, reactions
    
    def _calculate_reactions(self, u_global: np.ndarray) -> Dict:
        """Calculate support reactions."""
        # F = K * u (for all DOF including constrained)
        F_all = self.K_global @ u_global
        
        reactions = {}
        for support in self.supports:
            node_id = support.node.id
            dof = self.dof_map[node_id]
            
            reactions[node_id] = {
                'fx': F_all[dof[0]] if support.node.constrained_ux else 0.0,
                'fy': F_all[dof[1]] if support.node.constrained_uy else 0.0,
                'mz': F_all[dof[2]] if support.node.constrained_rz else 0.0
            }
            
            # Update node reactions
            support.node.fx = reactions[node_id]['fx']
            support.node.fy = reactions[node_id]['fy']
            support.node.mz = reactions[node_id]['mz']
        
        return reactions
    
    def _check_stiffness_matrix(self) -> bool:
        """Check if reduced stiffness matrix is non-singular using condition number."""
        try:
            K_ff = self.K_global[np.ix_(self.free_dof, self.free_dof)]
            cond = np.linalg.cond(K_ff)
            return cond < 1e12
        except Exception:
            return False
