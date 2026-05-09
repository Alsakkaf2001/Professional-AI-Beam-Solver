"""
Example: Simple cantilever beam
Demonstrates FEM solver usage without web interface
"""

import sys
sys.path.insert(0, '.')

from backend.fem.model import StructuralModel
from backend.fem.materials import Material
from backend.fem.sections import CrossSection
from backend.fem.supports import SupportType


def cantilever_example():
    """Create and solve a simple cantilever beam."""
    
    print("=" * 60)
    print("Professional AI Beam Solver - Example: Cantilever Beam")
    print("=" * 60)
    print()
    
    # Create model
    print("1. Creating structural model...")
    model = StructuralModel("Cantilever Beam Example")
    
    # Add nodes
    print("2. Adding nodes...")
    node1 = model.add_node(0, 0)        # Fixed support
    node2 = model.add_node(2000, 0)     # Mid span
    node3 = model.add_node(4000, 0)     # Free end
    print(f"   - {node1}")
    print(f"   - {node2}")
    print(f"   - {node3}")
    
    # Add elements
    print("3. Adding beam elements...")
    material = Material.steel()
    section = CrossSection.ipe('IPE-200')
    
    elem1 = model.add_element(node1.id, node2.id, material, section)
    elem2 = model.add_element(node2.id, node3.id, material, section)
    print(f"   - {elem1}")
    print(f"   - {elem2}")
    
    # Add support
    print("4. Adding supports...")
    sup = model.add_support(node1.id, SupportType.FIXED)
    print(f"   - {sup}")
    
    # Add loads
    print("5. Adding loads...")
    load1 = model.add_point_load(node3.id, fx=0, fy=-50)  # 50 kN downward
    print(f"   - {load1}")
    
    # Validate
    print()
    print("6. Validating structure...")
    is_valid, errors, warnings = model.validate()
    
    if errors:
        print(f"   Errors: {len(errors)}")
        for err in errors:
            print(f"      - {err}")
        print("   ✗ Cannot solve due to errors")
        return
    else:
        print("   ✓ No errors")
    
    if warnings:
        print(f"   Warnings: {len(warnings)}")
        for warn in warnings:
            print(f"      - {warn}")
    
    # Print validation report
    print()
    print("Validation Report:")
    print("-" * 60)
    print(model.validation_report)
    print("-" * 60)
    
    # Solve
    print()
    print("7. Solving structure...")
    try:
        results = model.solve()
        print("   ✓ Structure solved successfully")
    except Exception as e:
        print(f"   ✗ Solving failed: {e}")
        return
    
    # Display results
    print()
    print("RESULTS:")
    print("=" * 60)
    
    print("\nDisplacements:")
    for disp in results['displacements']:
        if abs(disp['magnitude']) > 1e-6:  # Only non-zero
            print(f"  Node {disp['node_id']}: UY = {disp['uy']:.4f} mm, RZ = {disp['rz']:.6f} rad")
    
    print("\nReactions:")
    for react in results['reactions']:
        print(f"  Node {react['node_id']}: Fy = {react['fy']:.2f} kN, Mz = {react['mz']:.2f} kN·m")
    
    print("\nShear Force & Bending Moment:")
    for elem_key, diagram in results['diagrams'].items():
        elem_id = diagram['element_id']
        max_sfd = max(diagram['shear_forces'], key=abs)
        max_bmd = max(diagram['bending_moments'], key=abs)
        print(f"  Element {elem_id}:")
        print(f"    Max Shear: {max_sfd:.2f} kN")
        print(f"    Max Moment: {max_bmd:.2f} kN·m")
    
    print()
    print("=" * 60)
    print("✓ Example completed successfully")
    print("=" * 60)
    
    return model


def simply_supported_example():
    """Create and solve a simply supported beam with UDL."""
    
    print("\n" * 2)
    print("=" * 60)
    print("Example: Simply Supported Beam with Distributed Load")
    print("=" * 60)
    print()
    
    # Create model
    print("1. Creating model...")
    model = StructuralModel("Simply Supported Beam")
    
    # Add nodes
    print("2. Adding nodes...")
    node1 = model.add_node(0, 0)
    node2 = model.add_node(2000, 0)
    node3 = model.add_node(4000, 0)
    
    # Add elements
    print("3. Adding elements...")
    material = Material.steel()
    section = CrossSection.ipe('IPE-300')
    
    elem1 = model.add_element(node1.id, node2.id, material, section)
    elem2 = model.add_element(node2.id, node3.id, material, section)
    
    # Add supports (pin and roller)
    print("4. Adding supports...")
    model.add_support(node1.id, SupportType.PIN)
    model.add_support(node3.id, SupportType.ROLLER_Y)
    
    # Add distributed load
    print("5. Adding distributed load...")
    model.add_distributed_load(elem1.id, q_start=20, direction='y')
    model.add_distributed_load(elem2.id, q_start=20, direction='y')
    
    # Validate
    print()
    print("6. Validating...")
    is_valid, errors, warnings = model.validate()
    if not is_valid:
        print(f"   Validation failed: {errors}")
        return
    print("   ✓ Valid")
    
    # Solve
    print("\n7. Solving...")
    try:
        results = model.solve()
        print("   ✓ Solved")
    except Exception as e:
        print(f"   ✗ Failed: {e}")
        return
    
    # Results
    print("\nRESULTS:")
    print("-" * 60)
    
    max_displacement = max(d['magnitude'] for d in results['displacements'])
    print(f"Max Displacement: {max_displacement:.4f} mm")
    
    for react in results['reactions']:
        print(f"Node {react['node_id']} Reaction: Fy = {react['fy']:.2f} kN")
    
    print("=" * 60)


if __name__ == '__main__':
    # Run examples
    cantilever_example()
    simply_supported_example()
