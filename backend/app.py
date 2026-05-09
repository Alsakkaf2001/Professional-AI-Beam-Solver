"""Main Flask application."""
import os
import json
import traceback
from dotenv import load_dotenv

# Load .env from the project root (one level above backend/)
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from werkzeug.utils import secure_filename

from fem.model import StructuralModel
from fem.nodes import Node
from fem.elements import BeamElement2D
from fem.materials import Material
from fem.sections import CrossSection
from fem.supports import Support, SupportType
from fem.loads import PointLoad, DistributedLoad

FRONTEND_FOLDER = os.path.join(os.path.dirname(__file__), '..', 'frontend')
UPLOAD_FOLDER  = os.path.join(os.path.dirname(__file__), '..', 'uploads')
REPORT_FOLDER  = os.path.join(os.path.dirname(__file__), '..', 'reports')

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(REPORT_FOLDER, exist_ok=True)

app = Flask(__name__, static_folder=FRONTEND_FOLDER, static_url_path='')
CORS(app)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

# ── helpers ───────────────────────────────────────────────────────────────────

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def _reset_id_counters():
    Node._node_id_counter = 0
    BeamElement2D._element_id_counter = 0
    Support._support_id_counter = 0
    PointLoad._load_id_counter = 0
    DistributedLoad._load_id_counter = 0


def _get_material(name: str) -> Material:
    name = (name or 'steel').lower()
    if name == 'aluminum':
        return Material.aluminum()
    if name == 'concrete':
        return Material.concrete()
    return Material.steel()


def _get_section(name: str) -> CrossSection:
    db = CrossSection.STANDARD_SECTIONS
    if name in db:
        s = db[name]
        return CrossSection(name, s['A'], s['I'])
    s = db['IPE-200']
    return CrossSection('IPE-200', s['A'], s['I'])


def _normalise_ai_model(data: dict) -> dict:
    """
    Gemini (and other LLMs) may return slightly different field names.
    Normalise everything to the schema the FEM solver expects.
    """
    # elements: n1/n2 → node_i/node_j
    for el in data.get('elements', []):
        if 'n1' in el and 'node_i' not in el:
            el['node_i'] = el.pop('n1')
        if 'n2' in el and 'node_j' not in el:
            el['node_j'] = el.pop('n2')

    # supports: node → node_id; support_type → type
    for sup in data.get('supports', []):
        if 'node' in sup and 'node_id' not in sup:
            sup['node_id'] = sup.pop('node')
        if 'support_type' in sup and 'type' not in sup:
            sup['type'] = sup.pop('support_type')
        # normalise type values
        t = sup.get('type', '').lower().replace(' ', '_')
        sup['type'] = t if t in ('pin', 'fixed', 'roller_x', 'roller_y') else 'pin'

    # loads: node → node_id; fy → magnitude_kN + direction
    for ld in data.get('loads', []):
        if 'node' in ld and 'node_id' not in ld:
            ld['node_id'] = ld.pop('node')
        # If raw fy/fx given, convert to magnitude_kN + direction
        if 'fy' in ld and 'magnitude_kN' not in ld:
            fy = float(ld.pop('fy'))
            ld.setdefault('type', 'point')
            ld['magnitude_kN'] = abs(fy)
            ld['direction']    = 'down' if fy < 0 else 'up'
        if 'fx' in ld and 'magnitude_kN' not in ld:
            fx = float(ld.pop('fx'))
            ld.setdefault('type', 'point')
            ld['magnitude_kN'] = abs(fx)
            ld['direction']    = 'right' if fx > 0 else 'left'
        # element_id alias
        if 'element' in ld and 'element_id' not in ld:
            ld['element_id'] = ld.pop('element')

    return data


# ── frontend ──────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    return send_file(os.path.join(FRONTEND_FOLDER, 'index.html'))


# ── health ────────────────────────────────────────────────────────────────────

@app.route('/health')
def health():
    return jsonify({'status': 'healthy', 'service': 'Professional AI Beam Solver'})


# ── CORE SOLVE ENDPOINT ───────────────────────────────────────────────────────

@app.route('/api/solve-model', methods=['POST'])
def solve_model_direct():
    """
    Accept a complete model from the frontend and return FEM results.

    Expected JSON:
    {
      "nodes":    [{"id": 1, "x": 0, "y": 0}, ...],         -- canvas pixels
      "elements": [{"id": 1, "node_i": 1, "node_j": 2,
                    "material": "steel", "section": "IPE-200"}, ...],
      "supports": [{"id": 1, "node_id": 1, "type": "pin"}, ...],
      "loads":    [
        {"id":1, "type":"point",       "node_id":2,    "value":10},
        {"id":2, "type":"distributed", "element_id":1, "value":5}
      ],
      "scale": 10   -- mm per canvas pixel (default 10)
    }
    """
    try:
        data = request.get_json(force=True)
        SCALE = float(data.get('scale', 10))  # mm per canvas unit

        _reset_id_counters()
        model = StructuralModel('Solve')

        # ── nodes ──
        node_map = {}   # canvas_id → backend_id
        for nd in data.get('nodes', []):
            # Flip Y: screen Y-down → structural Y-up
            x_mm = nd['x'] * SCALE
            y_mm = -nd['y'] * SCALE
            node = model.add_node(x_mm, y_mm)
            node_map[nd['id']] = node.id

        # ── elements ──
        elem_map = {}
        for el in data.get('elements', []):
            ni = node_map.get(el['node_i'])
            nj = node_map.get(el['node_j'])
            if ni is None or nj is None:
                continue
            mat = _get_material(el.get('material', 'steel'))
            sec = _get_section(el.get('section', 'IPE-200'))
            elem = model.add_element(ni, nj, mat, sec)
            elem_map[el['id']] = elem.id

        # ── supports ──
        for sup in data.get('supports', []):
            nid = node_map.get(sup['node_id'])
            if nid is None:
                continue
            stype = SupportType(sup['type'])
            model.add_support(nid, stype)

        # ── loads ──
        for ld in data.get('loads', []):
            if ld['type'] == 'point':
                nid = node_map.get(ld['node_id'])
                if nid is None:
                    continue
                # value > 0 means downward force (−Y in structural coords)
                val = float(ld.get('value', 0))
                fx  = float(ld.get('fx', 0))
                fy  = float(ld.get('fy', -val))   # downward = negative kN
                mz  = float(ld.get('mz', 0))
                model.add_point_load(nid, fx=fx, fy=fy, mz=mz)

            elif ld['type'] == 'distributed':
                eid = elem_map.get(ld['element_id'])
                if eid is None:
                    continue
                val = float(ld.get('value', 0))   # kN/m downward
                model.add_distributed_load(eid, q_start=-val, q_end=-val)

        # ── solve ──
        raw = model.solve()

        # ── unit conversion for response ──
        # displacements already in mm (FEM output)
        displacements = raw['displacements']
        # reactions stored in N on nodes → convert to kN / kN·m
        reactions = []
        for nd in model.nodes:
            if nd.constrained_ux or nd.constrained_uy or nd.constrained_rz:
                reactions.append({
                    'node_id': nd.id,
                    'fx': round(nd.fx / 1000, 4),       # N → kN
                    'fy': round(nd.fy / 1000, 4),
                    'mz': round(nd.mz / 1.0e6, 4),      # N·mm → kN·m
                    'x': nd.x,
                    'y': nd.y
                })

        # diagrams: SFD/BMD values are in local element forces (N and N·mm) → kN / kN·m
        diagrams = raw.get('diagrams', {})
        for key, diag in diagrams.items():
            diag['shear_forces']    = [v / 1000   for v in diag['shear_forces']]
            diag['bending_moments'] = [v / 1.0e6  for v in diag['bending_moments']]

        # summary stats
        all_disp = [abs(d['uy']) for d in displacements]
        max_disp = max(all_disp) if all_disp else 0

        return jsonify({
            'success': True,
            'displacements': displacements,
            'reactions': reactions,
            'diagrams': diagrams,
            'summary': {
                'max_displacement_mm': round(max_disp, 4),
                'total_vertical_reaction_kN': round(sum(r['fy'] for r in reactions), 3)
            },
            'validation': raw.get('validation', '')
        })

    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500


# ── AI EXTRACTION ─────────────────────────────────────────────────────────────

@app.route('/api/ai/extract', methods=['POST'])
def ai_extract():
    try:
        if 'image' not in request.files:
            return jsonify({'success': False, 'error': 'No image provided'}), 400
        file = request.files['image']
        if not allowed_file(file.filename):
            return jsonify({'success': False, 'error': 'Invalid file type'}), 400

        filename = secure_filename(file.filename)
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        file.save(filepath)

        from ai.image_extractor import StructuralImageExtractor
        api_key = os.getenv('LEMONFOX_API_KEY')
        extractor = StructuralImageExtractor(api_key)

        result     = extractor.extract_and_build(filepath, auto_repair=True)
        raw_data   = result['repaired_data']

        # normalise field names (n1/n2 → node_i/node_j, etc.)
        raw_data   = _normalise_ai_model(raw_data)

        validation = extractor.validate_extraction(raw_data)
        result['validation']   = validation
        result['repaired_data'] = raw_data

        # ── convert to canvas model (pixels) ──────────────────────────
        # Gemini returns real-world metres; map to canvas units (÷ CANVAS_SCALE)
        # so that 1 canvas unit = 10 mm = 0.01 m → multiply metres by 100
        CANVAS_SCALE = 10   # mm per canvas unit (matches frontend)
        M_TO_CANVAS  = 1000 / CANVAS_SCALE   # 1 m = 100 canvas units

        canvas_nodes = []
        for nd in raw_data.get('nodes', []):
            canvas_nodes.append({
                'id': nd['id'],
                'x':  round(nd['x'] * M_TO_CANVAS, 1),
                'y':  round(-nd['y'] * M_TO_CANVAS, 1)   # flip Y for canvas
            })

        canvas_elements = []
        for el in raw_data.get('elements', []):
            canvas_elements.append({
                'id':      el['id'],
                'node_i':  el['node_i'],
                'node_j':  el['node_j'],
                'material': el.get('material', 'steel'),
                'section':  el.get('section', 'IPE-200')
            })

        canvas_supports = []
        for i, sup in enumerate(raw_data.get('supports', []), 1):
            canvas_supports.append({
                'id':      i,
                'node_id': sup['node_id'],
                'type':    sup.get('type', 'pin')
            })

        canvas_loads = []
        for i, ld in enumerate(raw_data.get('loads', []), 1):
            direction = ld.get('direction', 'down')
            mag       = float(ld.get('magnitude_kN', 10))
            ltype     = ld.get('type', 'point')
            entry     = {'id': i, 'type': ltype, 'value': mag}
            if ltype == 'point':
                entry['node_id']    = ld.get('node_id')
            else:
                entry['element_id'] = ld.get('element_id')
            canvas_loads.append(entry)

        result['canvas_model'] = {
            'nodes':    canvas_nodes,
            'elements': canvas_elements,
            'supports': canvas_supports,
            'loads':    canvas_loads
        }

        return jsonify({
            'success':    validation['valid'] or len(validation['issues']) == 0,
            'extraction': result
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e),
                        'traceback': traceback.format_exc()}), 500


# ── EXPORT ────────────────────────────────────────────────────────────────────

@app.route('/api/export/pdf', methods=['POST'])
def export_pdf():
    try:
        from exports.pdf_report import generate_pdf_report
        data = request.get_json(force=True) or {}
        filename = secure_filename(data.get('filename', 'report.pdf'))
        filepath = os.path.join(REPORT_FOLDER, filename)
        model_data = data.get('model')
        results_data = data.get('results')
        generate_pdf_report(model_data, results_data, filepath)
        return send_file(filepath, as_attachment=True, download_name=filename,
                         mimetype='application/pdf')
    except Exception as e:
        return jsonify({'success': False, 'error': str(e),
                        'traceback': traceback.format_exc()}), 500


@app.route('/api/export/dxf', methods=['POST'])
def export_dxf():
    try:
        from exports.dxf_export import export_to_dxf
        data = request.get_json(force=True) or {}
        filename = secure_filename(data.get('filename', 'model.dxf'))
        filepath = os.path.join(REPORT_FOLDER, filename)
        export_to_dxf(data.get('model'), filepath)
        return send_file(filepath, as_attachment=True, download_name=filename,
                         mimetype='application/dxf')
    except Exception as e:
        return jsonify({'success': False, 'error': str(e),
                        'traceback': traceback.format_exc()}), 500


# ── ERROR HANDLERS ────────────────────────────────────────────────────────────

@app.errorhandler(404)
def not_found(e):
    return jsonify({'success': False, 'error': 'Endpoint not found'}), 404

@app.errorhandler(500)
def server_error(e):
    return jsonify({'success': False, 'error': 'Internal server error'}), 500


if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)
