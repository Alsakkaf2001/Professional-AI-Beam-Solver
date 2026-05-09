"""Structural validation before solving."""
from typing import List, Dict, Tuple
from .nodes import Node
from .elements import BeamElement2D
from .supports import Support
from .loads import PointLoad, DistributedLoad


class ValidationError(Exception):
    """Raised when structure validation fails."""
    pass


class StructuralValidator:
    """Validates structural models before solving."""
    
    def __init__(self, nodes: List[Node], elements: List[BeamElement2D], 
                 supports: List[Support], loads: List[PointLoad] = None):
        """Initialize validator."""
        self.nodes = nodes
        self.elements = elements
        self.supports = supports
        self.loads = loads or []
        self.warnings = []
        self.errors = []
    
    def validate_all(self) -> Tuple[bool, List[str], List[str]]:
        """
        Run all validations.
        
        Returns:
            (is_valid, errors, warnings)
        """
        self.errors = []
        self.warnings = []
        
        self._validate_basic_structure()
        self._validate_supports()
        self._validate_connectivity()
        self._validate_stability()
        
        return (len(self.errors) == 0, self.errors, self.warnings)
    
    def _validate_basic_structure(self):
        """Check basic structural health."""
        if not self.nodes:
            self.errors.append("No nodes defined")
        if not self.elements:
            self.errors.append("No elements defined")
        
        # Check for zero-length elements
        for elem in self.elements:
            if elem.L < 1e-3:
                self.errors.append(f"Element {elem.id}: zero-length member (L={elem.L}mm)")
    
    def _validate_supports(self):
        """Check support configuration."""
        if not self.supports:
            self.errors.append("No supports defined (structure is unstable)")
            return
        
        # Count constrained DOFs
        constrained_dofs = 0
        for support in self.supports:
            if support.node.constrained_ux:
                constrained_dofs += 1
            if support.node.constrained_uy:
                constrained_dofs += 1
            if support.node.constrained_rz:
                constrained_dofs += 1
        
        # Check if at least 3 DOF are constrained for 2D
        if constrained_dofs < 3:
            self.errors.append(
                f"Insufficient supports: {constrained_dofs} DOF constrained (need minimum 3 for 2D stability)"
            )
        
        # Check for improper/redundant support combinations
        if constrained_dofs < 6:
            for node in self.nodes:
                if (node.constrained_ux and node.constrained_uy and node.constrained_rz):
                    self.warnings.append(f"Node {node.id}: fully fixed support (hyperstatic structure)")
    
    def _validate_connectivity(self):
        """Check connected structure (no disconnected components)."""
        if not self.nodes or not self.elements:
            return
        
        # Build adjacency from elements
        adjacency = {node.id: set() for node in self.nodes}
        for elem in self.elements:
            adjacency[elem.node_i.id].add(elem.node_j.id)
            adjacency[elem.node_j.id].add(elem.node_i.id)
        
        # Check if all elements are connected via a single graph
        visited = set()
        start_node = self.elements[0].node_i.id
        
        def dfs(node_id):
            visited.add(node_id)
            for neighbor in adjacency[node_id]:
                if neighbor not in visited:
                    dfs(neighbor)
        
        dfs(start_node)
        
        if len(visited) < len(self.nodes):
            self.errors.append("Structure has disconnected nodes")
    
    def _validate_stability(self):
        """Check for mechanisms (unstable structure)."""
        # For a 2D structure with n nodes and m members:
        # Stability requires: m >= 2n - 3 (for statically determinate/indeterminate)
        # But with supports, a more complex analysis is needed
        
        n_nodes = len(self.nodes)
        n_elements = len(self.elements)
        
        # Count supported nodes
        supported_nodes = set(sup.node.id for sup in self.supports)
        n_supported = len(supported_nodes)
        
        if n_supported == 0:
            self.errors.append("No supported nodes")
        
        # Simple heuristic: 2D frame needs m >= 2n - 3
        # But this is a rough check
        if n_elements < 2 * n_nodes - 3 and n_supported < 3:
            self.warnings.append("Potential mechanism or unstable structure")
    
    def get_report(self) -> str:
        """Get validation report."""
        report = "STRUCTURAL VALIDATION REPORT\n"
        report += "=" * 50 + "\n"
        report += f"Nodes: {len(self.nodes)}\n"
        report += f"Elements: {len(self.elements)}\n"
        report += f"Supports: {len(self.supports)}\n"
        report += f"Loads: {len(self.loads)}\n\n"
        
        if self.errors:
            report += "ERRORS:\n"
            for err in self.errors:
                report += f"  ✗ {err}\n"
        else:
            report += "✓ No structural errors\n\n"
        
        if self.warnings:
            report += "WARNINGS:\n"
            for warn in self.warnings:
                report += f"  ⚠ {warn}\n"
        else:
            report += "✓ No warnings\n"
        
        return report
