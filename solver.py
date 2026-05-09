"""
Standalone FEM Solver Module
Use the FEM solver without Flask backend
"""

from backend.fem.model import StructuralModel
from backend.fem.materials import Material
from backend.fem.sections import CrossSection
from backend.fem.supports import SupportType
from backend.fem.loads import PointLoad
import json


class StandaloneBeamSolver:
    """Standalone beam analysis solver."""
    
    def __init__(self):
        self.model = None
    
    def create_model(self, name="Structure"):
        """Create new model."""
        self.model = StructuralModel(name)
        return self.model
    
    def add_node(self, x, y):
        """Add node to model."""
        if not self.model:
            raise ValueError("Create model first")
        return self.model.add_node(x, y)
    
    def add_beam(self, node_i_id, node_j_id, material='steel', section='IPE-200'):
        """Add beam element."""
        if not self.model:
            raise ValueError("Create model first")
        
        # Get or create material
        if isinstance(material, str):
            mat = Material.steel() if material == 'steel' else Material.aluminum()
        else:
            mat = material
        
        # Get or create section
        if isinstance(section, str):
            sec = CrossSection.ipe(section) if section.startswith('IPE') else CrossSection.heb(section)
        else:
            sec = section
        
        return self.model.add_element(node_i_id, node_j_id, mat, sec)
    
    def add_pin_support(self, node_id):
        """Add pin support."""
        if not self.model:
            raise ValueError("Create model first")
        return self.model.add_support(node_id, SupportType.PIN)
    
    def add_fixed_support(self, node_id):
        """Add fixed support."""
        if not self.model:
            raise ValueError("Create model first")
        return self.model.add_support(node_id, SupportType.FIXED)
    
    def add_load(self, node_id, fx=0, fy=0, mz=0):
        """Add point load."""
        if not self.model:
            raise ValueError("Create model first")
        return self.model.add_point_load(node_id, fx, fy, mz)
    
    def validate(self):
        """Validate structure."""
        if not self.model:
            raise ValueError("Create model first")
        return self.model.validate()
    
    def solve(self):
        """Solve structure."""
        if not self.model:
            raise ValueError("Create model first")
        return self.model.solve()
    
    def get_reactions(self):
        """Get support reactions."""
        if not self.model or not self.model.is_solved:
            raise ValueError("Solve first")
        return self.model.reactions
    
    def get_displacements(self):
        """Get node displacements."""
        if not self.model or not self.model.is_solved:
            raise ValueError("Solve first")
        return self.model.displacements
    
    def export_json(self, filename):
        """Export to JSON."""
        if not self.model:
            raise ValueError("Create model first")
        with open(filename, 'w') as f:
            f.write(self.model.to_json())
    
    def export_pdf(self, filename):
        """Export to PDF."""
        if not self.model or not self.model.is_solved:
            raise ValueError("Solve first")
        from backend.exports.pdf_report import generate_pdf_report
        generate_pdf_report(self.model, filename)
    
    def export_dxf(self, filename):
        """Export to DXF."""
        if not self.model:
            raise ValueError("Create model first")
        from backend.exports.dxf_export import export_to_dxf
        export_to_dxf(self.model, filename)


# Quick API
def create_cantilever(length=1000.0, load=10.0):
    """Quick cantilever example."""
    solver = StandaloneBeamSolver()
    solver.create_model("Cantilever")
    
    n1 = solver.add_node(0, 0)
    n2 = solver.add_node(length, 0)
    
    solver.add_beam(n1.id, n2.id)
    solver.add_fixed_support(n1.id)
    solver.add_load(n2.id, fy=-load)
    
    is_valid, errors, warnings = solver.validate()
    if not is_valid:
        return None, errors
    
    results = solver.solve()
    return results, None


if __name__ == '__main__':
    # Example usage
    results, errors = create_cantilever(length=2000.0, load=50.0)
    if errors:
        print(f"Errors: {errors}")
    else:
        print("Cantilever beam solved successfully")
        print(f"Max displacement: {max(d['magnitude'] for d in results['displacements']):.4f} mm")
