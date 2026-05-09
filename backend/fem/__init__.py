"""
Professional AI Beam Solver - FEM Solver Module
Main entry point for the solver package
"""

from .model import StructuralModel
from .nodes import Node
from .elements import BeamElement2D
from .materials import Material
from .sections import CrossSection
from .supports import Support, SupportType
from .loads import PointLoad, DistributedLoad
from .validator import StructuralValidator
from .assembly import GlobalAssembly
from .recovery import ResultsRecovery

__all__ = [
    'StructuralModel',
    'Node',
    'BeamElement2D',
    'Material',
    'CrossSection',
    'Support',
    'SupportType',
    'PointLoad',
    'DistributedLoad',
    'StructuralValidator',
    'GlobalAssembly',
    'ResultsRecovery'
]

__version__ = '1.0.0'
