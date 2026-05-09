"""Main FEM model combining all components."""
import json
from typing import List, Dict, Tuple
from .nodes import Node
from .elements import BeamElement2D
from .materials import Material
from .sections import CrossSection
from .supports import Support, SupportType
from .loads import PointLoad, DistributedLoad
from .validator import StructuralValidator
from .assembly import GlobalAssembly
from .recovery import ResultsRecovery


class StructuralModel:
    """Complete FEM structural model."""
    
    def __init__(self, name: str = "Unnamed Structure"):
        """Initialize structural model."""
        self.name = name
        self.nodes: List[Node] = []
        self.elements: List[BeamElement2D] = []
        self.materials: List[Material] = []
        self.sections: List[CrossSection] = []
        self.supports: List[Support] = []
        self.point_loads: List[PointLoad] = []
        self.distributed_loads: List[DistributedLoad] = []
        
        # Solved data
        self.is_solved = False
        self.displacements = None
        self.reactions = None
        self.diagrams = None
        self.validation_report = None
    
    # ========== Node Management ==========
    def add_node(self, x: float, y: float) -> Node:
        """Add node to structure."""
        node = Node(x, y)
        self.nodes.append(node)
        return node
    
    def get_node(self, node_id: int) -> Node:
        """Get node by ID."""
        for node in self.nodes:
            if node.id == node_id:
                return node
        return None
    
    # ========== Element Management ==========
    def add_element(self, node_i_id: int, node_j_id: int, 
                   material: Material, section: CrossSection) -> BeamElement2D:
        """Add beam element."""
        node_i = self.get_node(node_i_id)
        node_j = self.get_node(node_j_id)
        
        if not node_i or not node_j:
            raise ValueError(f"Invalid nodes: {node_i_id}, {node_j_id}")
        
        elem = BeamElement2D(node_i, node_j, material, section)
        self.elements.append(elem)
        
        # Track material and section
        if material not in self.materials:
            self.materials.append(material)
        if section not in self.sections:
            self.sections.append(section)
        
        return elem
    
    def get_element(self, elem_id: int) -> BeamElement2D:
        """Get element by ID."""
        for elem in self.elements:
            if elem.id == elem_id:
                return elem
        return None
    
    # ========== Support Management ==========
    def add_support(self, node_id: int, support_type: SupportType) -> Support:
        """Add support to node."""
        node = self.get_node(node_id)
        if not node:
            raise ValueError(f"Invalid node: {node_id}")
        
        support = Support(node, support_type)
        self.supports.append(support)
        return support
    
    # ========== Load Management ==========
    def add_point_load(self, node_id: int, fx: float = 0.0, 
                      fy: float = 0.0, mz: float = 0.0) -> PointLoad:
        """Add point load."""
        node = self.get_node(node_id)
        if not node:
            raise ValueError(f"Invalid node: {node_id}")
        
        load = PointLoad(node, fx, fy, mz)
        self.point_loads.append(load)
        return load
    
    def add_distributed_load(self, element_id: int, q_start: float,
                           q_end: float = None, direction: str = 'y') -> DistributedLoad:
        """Add distributed load."""
        if not self.get_element(element_id):
            raise ValueError(f"Invalid element: {element_id}")
        
        load = DistributedLoad(element_id, q_start, q_end, direction=direction)
        self.distributed_loads.append(load)
        return load
    
    # ========== Validation ==========
    def validate(self) -> Tuple[bool, List[str], List[str]]:
        """Validate structure before solving."""
        validator = StructuralValidator(
            self.nodes, self.elements, self.supports, self.point_loads
        )
        is_valid, errors, warnings = validator.validate_all()
        self.validation_report = validator.get_report()
        return is_valid, errors, warnings
    
    # ========== Solving ==========
    def solve(self) -> Dict:
        """
        Solve the structure.
        
        Returns:
            Dictionary with results
        """
        # Validate first
        is_valid, errors, warnings = self.validate()
        
        if not is_valid:
            raise ValueError(f"Structure validation failed:\n{self.validation_report}")
        
        # Assemble and solve
        assembly = GlobalAssembly(
            self.nodes, self.elements, self.supports,
            self.point_loads, self.distributed_loads
        )
        
        try:
            u_global, reactions = assembly.solve()
        except Exception as e:
            raise ValueError(f"Solution failed: {e}")
        
        # Recovery
        recovery = ResultsRecovery(self.nodes, self.elements, self.point_loads)
        
        displacements = recovery.get_displacements()
        reactions_list = recovery.get_reactions()
        diagrams = recovery.compute_global_diagrams()
        
        # Store results
        self.is_solved = True
        self.displacements = displacements
        self.reactions = reactions_list
        self.diagrams = diagrams
        
        return {
            'success': True,
            'displacements': displacements,
            'reactions': reactions_list,
            'diagrams': diagrams,
            'validation': self.validation_report
        }
    
    # ========== Serialization ==========
    def to_dict(self) -> Dict:
        """Serialize model to dictionary."""
        return {
            'name': self.name,
            'nodes': [node.to_dict() for node in self.nodes],
            'materials': [mat.to_dict() for mat in self.materials],
            'sections': [sec.to_dict() for sec in self.sections],
            'elements': [elem.to_dict() for elem in self.elements],
            'supports': [sup.to_dict() for sup in self.supports],
            'point_loads': [load.to_dict() for load in self.point_loads],
            'distributed_loads': [load.to_dict() for load in self.distributed_loads]
        }
    
    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), indent=2)
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'StructuralModel':
        """Deserialize from dictionary."""
        model = cls(data['name'])
        
        # Rebuild nodes
        node_map = {}
        for node_data in data['nodes']:
            node = Node.from_dict(node_data)
            model.nodes.append(node)
            node_map[node.id] = node
        
        # Rebuild materials and sections
        mat_map = {}
        for mat_data in data['materials']:
            mat = Material.from_dict(mat_data)
            model.materials.append(mat)
            mat_map[mat.id] = mat
        
        sec_map = {}
        for sec_data in data['sections']:
            sec = CrossSection.from_dict(sec_data)
            model.sections.append(sec)
            sec_map[sec.id] = sec
        
        # Rebuild elements
        for elem_data in data['elements']:
            node_i = node_map[elem_data['node_i']]
            node_j = node_map[elem_data['node_j']]
            mat = mat_map[elem_data['material']['id']]
            sec = sec_map[elem_data['section']['id']]
            
            elem = BeamElement2D(node_i, node_j, mat, sec, elem_data['id'])
            model.elements.append(elem)
        
        # Rebuild supports
        for sup_data in data.get('supports', []):
            node = node_map[sup_data['node_id']]
            sup_type = SupportType(sup_data['type'])
            sup = Support(node, sup_type, sup_data['id'])
            model.supports.append(sup)
        
        # Rebuild loads
        for load_data in data.get('point_loads', []):
            node = node_map[load_data['node_id']]
            load = PointLoad(
                node, load_data['fx'], load_data['fy'],
                load_data.get('mz', 0.0), load_data['id']
            )
            model.point_loads.append(load)
        
        for load_data in data.get('distributed_loads', []):
            load = DistributedLoad.from_dict(load_data)
            model.distributed_loads.append(load)
        
        return model
    
    @classmethod
    def from_json(cls, json_str: str) -> 'StructuralModel':
        """Deserialize from JSON string."""
        data = json.loads(json_str)
        return cls.from_dict(data)
    
    def __repr__(self) -> str:
        return (f"StructuralModel({self.name}, nodes={len(self.nodes)}, "
                f"elements={len(self.elements)}, supports={len(self.supports)})")
