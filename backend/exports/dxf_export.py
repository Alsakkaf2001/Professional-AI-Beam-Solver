"""DXF export — accepts plain dict model."""
import ezdxf


def export_to_dxf(model_data: dict, filepath: str):
    """Export model dict to DXF file."""
    model_data = model_data or {}
    nodes    = {n['id']: n for n in model_data.get('nodes', [])}
    elements = model_data.get('elements', [])
    supports = model_data.get('supports', [])
    loads    = model_data.get('loads', [])
    SCALE    = model_data.get('scale', 10)  # mm per canvas unit

    doc = ezdxf.new('R2010')
    msp = doc.modelspace()

    for layer, col in [('Nodes', 5), ('Beams', 3), ('Supports', 1),
                        ('Loads', 2), ('Labels', 7)]:
        doc.layers.new(name=layer, dxfattribs={'color': col})

    # ── nodes ──
    for nid, nd in nodes.items():
        x, y = nd['x'] * SCALE, -nd['y'] * SCALE
        msp.add_circle((x, y), radius=50, dxfattribs={'layer': 'Nodes'})
        msp.add_text(f"N{nid}", dxfattribs={'height': 40, 'layer': 'Labels'}) \
           .set_placement((x + 60, y + 60))

    # ── elements ──
    for el in elements:
        ni = nodes.get(el['node_i'])
        nj = nodes.get(el['node_j'])
        if ni and nj:
            x1, y1 = ni['x'] * SCALE, -ni['y'] * SCALE
            x2, y2 = nj['x'] * SCALE, -nj['y'] * SCALE
            msp.add_line((x1, y1), (x2, y2), dxfattribs={'layer': 'Beams', 'lineweight': 25})
            mx, my = (x1 + x2) / 2, (y1 + y2) / 2
            msp.add_text(f"E{el['id']}", dxfattribs={'height': 35, 'layer': 'Labels'}) \
               .set_placement((mx, my + 50))

    # ── supports ──
    for sup in supports:
        nd = nodes.get(sup['node_id'])
        if not nd:
            continue
        x, y = nd['x'] * SCALE, -nd['y'] * SCALE
        stype = sup.get('type', 'pin')
        if stype == 'pin':
            pts = [(x - 40, y), (x + 40, y), (x, y - 60), (x - 40, y)]
            msp.add_lwpolyline(pts, dxfattribs={'layer': 'Supports'})
        elif stype == 'fixed':
            pts = [(x - 50, y - 60), (x + 50, y - 60), (x + 50, y), (x - 50, y), (x - 50, y - 60)]
            msp.add_lwpolyline(pts, dxfattribs={'layer': 'Supports'})
        else:
            msp.add_circle((x, y - 30), radius=30, dxfattribs={'layer': 'Supports'})

    # ── point loads ──
    for ld in loads:
        if ld.get('type') == 'point':
            nd = nodes.get(ld.get('node_id'))
            if nd:
                x, y = nd['x'] * SCALE, -nd['y'] * SCALE
                val = ld.get('value', 10)
                msp.add_line((x, y), (x, y + 200), dxfattribs={'layer': 'Loads'})
                msp.add_text(f"{val}kN", dxfattribs={'height': 35, 'layer': 'Labels'}) \
                   .set_placement((x + 20, y + 100))

    doc.saveas(filepath)
