/**
 * Professional AI Beam Solver — Main Application
 */

const API = 'http://127.0.0.1:5000/api';
const CANVAS_SCALE = 10;   // mm per canvas world-unit

class BeamSolverApp {
    constructor() {
        this.canvas = new Canvas(document.getElementById('canvas'));

        this.currentTool = 'select';
        this.material    = 'steel';
        this.section     = 'IPE-200';
        this.supportType = 'pin';
        this.loadValue   = 10;
        this.beamStart   = null;

        this.lastResults = null;

        this.setupEventListeners();
        this.updateStatus();
        this.log('Professional AI Beam Solver v1.0 — ready');
    }

    // ═══ EVENT SETUP ═══════════════════════════════════════════════════════

    setupEventListeners() {
        document.querySelectorAll('.tool-btn[data-tool]').forEach(btn => {
            btn.addEventListener('click', () => this.selectTool(btn.dataset.tool));
        });

        document.getElementById('btn-new').addEventListener('click', () => this.newModel());
        document.getElementById('btn-load').addEventListener('click', () => this.loadModel());
        document.getElementById('btn-save').addEventListener('click', () => this.saveModel());

        const cvs = document.getElementById('canvas');
        cvs.addEventListener('click',       e => this.handleCanvasClick(e));
        cvs.addEventListener('mousemove',   e => this.handleCanvasMove(e));
        cvs.addEventListener('wheel',       e => this.handleCanvasWheel(e), { passive: false });
        cvs.addEventListener('contextmenu', e => e.preventDefault());

        let dragging = false, lastX = 0, lastY = 0;
        cvs.addEventListener('mousedown', e => {
            if (e.button === 1 || e.button === 2) { dragging = true; lastX = e.clientX; lastY = e.clientY; }
        });
        cvs.addEventListener('mousemove', e => {
            if (dragging) { this.canvas.pan_view(e.clientX - lastX, e.clientY - lastY); lastX = e.clientX; lastY = e.clientY; }
        });
        cvs.addEventListener('mouseup', () => { dragging = false; });

        document.querySelectorAll('.panel-tab-btn').forEach(btn => {
            btn.addEventListener('click', () => this.switchTab(btn.dataset.tab));
        });

        document.addEventListener('keydown', e => this.handleKeydown(e));

        document.getElementById('btn-fit-view').addEventListener('click',  () => this.canvas.fit_view());
        document.getElementById('btn-zoom-in').addEventListener('click',   () => this.canvas.zoom_in());
        document.getElementById('btn-zoom-out').addEventListener('click',  () => this.canvas.zoom_out());
        document.getElementById('btn-solve').addEventListener('click',     () => this.solve());
        document.getElementById('btn-validate').addEventListener('click',  () => this.validate());
        document.getElementById('btn-export-pdf').addEventListener('click',() => this.exportPDF());
        document.getElementById('btn-export-dxf').addEventListener('click',() => this.exportDXF());
        document.getElementById('btn-extract-image').addEventListener('click', () => this.openAIExtract());

        // Property panel changes
        document.getElementById('material-select').addEventListener('change', e => {
            this.material = e.target.value;
        });
        document.getElementById('section-select').addEventListener('change', e => {
            this.section = e.target.value;
        });
        document.getElementById('support-type-select').addEventListener('change', e => {
            this.supportType = e.target.value;
        });
        document.getElementById('load-value').addEventListener('input', e => {
            this.loadValue = parseFloat(e.target.value) || 10;
        });

        // AI modal
        document.getElementById('modal-extract-cancel').addEventListener('click', () => {
            document.getElementById('modal-ai-extract').classList.add('hidden');
        });
        document.getElementById('modal-extract-ok').addEventListener('click', () => this.runAIExtract());

        // Diagram toggle buttons
        ['btn-show-sfd','btn-show-bmd','btn-show-deformation'].forEach(id => {
            document.getElementById(id).addEventListener('click', () => {
                document.getElementById(id).classList.toggle('active');
                if (this.lastResults) this.renderDiagrams(this.lastResults);
            });
        });
    }

    // ═══ TOOL SELECTION ════════════════════════════════════════════════════

    selectTool(tool) {
        document.querySelectorAll('.tool-btn[data-tool]').forEach(btn => btn.classList.remove('active'));
        const btn = document.querySelector(`[data-tool="${tool}"]`);
        if (btn) btn.classList.add('active');
        this.currentTool = tool;
        this.beamStart = null;
        const cursors = { select:'pointer', node:'crosshair', beam:'crosshair',
                          support:'pointer', 'point-load':'pointer', udl:'pointer' };
        document.getElementById('canvas').style.cursor = cursors[tool] || 'default';
        document.getElementById('stat-mode').textContent = tool;
        this.updateStatus(`Tool: ${tool}`);
    }

    // ═══ CANVAS EVENTS ═════════════════════════════════════════════════════

    handleCanvasClick(e) {
        const rect = this.canvas.canvas.getBoundingClientRect();
        const sx = e.clientX - rect.left;
        const sy = e.clientY - rect.top;
        const hit = this.canvas.getElementAt(sx, sy);

        switch (this.currentTool) {
            case 'select':       this.handleSelect(hit); break;
            case 'node':         this.handleNodeTool(sx, sy); break;
            case 'beam':         this.handleBeamTool(hit); break;
            case 'support':      this.handleSupportTool(hit); break;
            case 'point-load':   this.handlePointLoadTool(hit); break;
            case 'udl':          this.handleUDLTool(hit); break;
        }
    }

    handleCanvasMove(e) {
        const rect = this.canvas.canvas.getBoundingClientRect();
        const { x, y } = this.canvas.screenToWorld(e.clientX - rect.left, e.clientY - rect.top);
        document.getElementById('stat-pos').textContent = `X:${(x * CANVAS_SCALE).toFixed(0)}mm Y:${(-y * CANVAS_SCALE).toFixed(0)}mm`;
        document.getElementById('stat-zoom').textContent = `${(this.canvas.zoom * 100).toFixed(0)}%`;
    }

    handleCanvasWheel(e) {
        e.preventDefault();
        if (e.deltaY < 0) this.canvas.zoom_in(); else this.canvas.zoom_out();
    }

    // ═══ TOOL HANDLERS ═════════════════════════════════════════════════════

    handleSelect(hit) {
        this.canvas.selectedNodeId    = null;
        this.canvas.selectedElementId = null;
        if (hit?.type === 'node')    { this.canvas.selectedNodeId    = hit.id; this.showNodeProperties(hit.obj); }
        if (hit?.type === 'element') { this.canvas.selectedElementId = hit.id; this.showElementProperties(hit.obj); }
        if (!hit) this.clearProperties();
        this.canvas.draw();
    }

    handleNodeTool(sx, sy) {
        const { x, y } = this.canvas.screenToWorld(sx, sy);
        const snap = 50;
        const node = { id: this._nextId(this.canvas.nodes), x: Math.round(x/snap)*snap, y: Math.round(y/snap)*snap };
        this.canvas.nodes.set(node.id, node);
        this.log(`Node ${node.id} at (${(node.x*CANVAS_SCALE).toFixed(0)}mm, ${(-node.y*CANVAS_SCALE).toFixed(0)}mm)`);
        this.updateStatus();
        this.canvas.draw();
    }

    handleBeamTool(hit) {
        if (!hit || hit.type !== 'node') { this.log('Click a node to start beam'); return; }
        if (!this.beamStart) { this.beamStart = hit.id; this.log(`Beam start: Node ${hit.id} — click end node`); return; }
        if (hit.id === this.beamStart) { this.log('Same node selected — cancelled'); this.beamStart = null; return; }

        const elem = { id: this._nextId(this.canvas.elements), node_i: this.beamStart, node_j: hit.id,
                       material: this.material, section: this.section };
        this.canvas.elements.set(elem.id, elem);
        this.log(`Element ${elem.id}: Node ${elem.node_i} → Node ${elem.node_j} [${elem.section}]`);
        this.beamStart = null;
        this.updateStatus();
        this.canvas.draw();
    }

    handleSupportTool(hit) {
        if (!hit || hit.type !== 'node') { this.log('Click a node to add support'); return; }
        const sup = { id: this._nextId(this.canvas.supports), node_id: hit.id, type: this.supportType };
        this.canvas.supports.set(sup.id, sup);
        this.log(`${sup.type} support at Node ${hit.id}`);
        this.updateStatus();
        this.canvas.draw();
    }

    handlePointLoadTool(hit) {
        if (!hit || hit.type !== 'node') { this.log('Click a node to add point load'); return; }
        const load = { id: this._nextId(this.canvas.loads), type: 'point',
                       node_id: hit.id, value: this.loadValue };
        this.canvas.loads.set(load.id, load);
        this.log(`${load.value}kN point load at Node ${hit.id}`);
        this.updateStatus();
        this.canvas.draw();
    }

    handleUDLTool(hit) {
        if (!hit || hit.type !== 'element') { this.log('Click an element to add UDL'); return; }
        const load = { id: this._nextId(this.canvas.loads), type: 'distributed',
                       element_id: hit.id, value: this.loadValue };
        this.canvas.loads.set(load.id, load);
        this.log(`${load.value}kN/m UDL on Element ${hit.id}`);
        this.updateStatus();
        this.canvas.draw();
    }

    _nextId(map) {
        let max = 0;
        for (const k of map.keys()) if (k > max) max = k;
        return max + 1;
    }

    // ═══ KEYBOARD ══════════════════════════════════════════════════════════

    handleKeydown(e) {
        if (e.target.tagName === 'INPUT' || e.target.tagName === 'SELECT') return;
        const map = { s:'select', n:'node', b:'beam', p:'support', l:'point-load', u:'udl' };
        if (map[e.key]) { e.preventDefault(); this.selectTool(map[e.key]); return; }
        if (e.key === 'Enter')  { e.preventDefault(); this.solve(); }
        if (e.key === 'Delete') { e.preventDefault(); this.deleteSelected(); }
        if (e.key === '+')      { e.preventDefault(); this.canvas.zoom_in(); }
        if (e.key === '-')      { e.preventDefault(); this.canvas.zoom_out(); }
        if (e.key === '0')      { e.preventDefault(); this.canvas.fit_view(); }
    }

    deleteSelected() {
        if (this.canvas.selectedNodeId) {
            const nid = this.canvas.selectedNodeId;
            this.canvas.nodes.delete(nid);
            for (const [id, el] of this.canvas.elements)
                if (el.node_i === nid || el.node_j === nid) this.canvas.elements.delete(id);
            for (const [id, sup] of this.canvas.supports)
                if (sup.node_id === nid) this.canvas.supports.delete(id);
            for (const [id, ld] of this.canvas.loads)
                if (ld.node_id === nid) this.canvas.loads.delete(id);
            this.canvas.selectedNodeId = null;
            this.log('Node deleted');
        } else if (this.canvas.selectedElementId) {
            const eid = this.canvas.selectedElementId;
            this.canvas.elements.delete(eid);
            for (const [id, ld] of this.canvas.loads)
                if (ld.element_id === eid) this.canvas.loads.delete(id);
            this.canvas.selectedElementId = null;
            this.log('Element deleted');
        }
        this.updateStatus();
        this.canvas.draw();
    }

    // ═══ MODEL OPERATIONS ══════════════════════════════════════════════════

    newModel() {
        this.canvas.nodes.clear(); this.canvas.elements.clear();
        this.canvas.supports.clear(); this.canvas.loads.clear();
        this.lastResults = null;
        this.clearProperties();
        this.canvas.fit_view();
        this.updateStatus();
        this.log('New model');
    }

    saveModel() {
        const data = {
            nodes:    [...this.canvas.nodes.values()],
            elements: [...this.canvas.elements.values()],
            supports: [...this.canvas.supports.values()],
            loads:    [...this.canvas.loads.values()]
        };
        const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
        const a = Object.assign(document.createElement('a'), { href: URL.createObjectURL(blob), download: 'model.json' });
        a.click();
        this.log('Model saved');
    }

    loadModel() {
        const input = Object.assign(document.createElement('input'), { type: 'file', accept: '.json' });
        input.onchange = e => {
            const reader = new FileReader();
            reader.onload = ev => {
                try {
                    const data = JSON.parse(ev.target.result);
                    this.canvas.nodes.clear(); this.canvas.elements.clear();
                    this.canvas.supports.clear(); this.canvas.loads.clear();
                    (data.nodes    || []).forEach(n => this.canvas.nodes.set(n.id, n));
                    (data.elements || []).forEach(n => this.canvas.elements.set(n.id, n));
                    (data.supports || []).forEach(n => this.canvas.supports.set(n.id, n));
                    (data.loads    || []).forEach(n => this.canvas.loads.set(n.id, n));
                    this.canvas.fit_view();
                    this.updateStatus();
                    this.log('Model loaded');
                } catch (err) { this.logError('Load failed: ' + err.message); }
            };
            reader.readAsText(e.target.files[0]);
        };
        input.click();
    }

    // ═══ VALIDATION ════════════════════════════════════════════════════════

    validate() {
        const issues = [];
        if (this.canvas.nodes.size === 0)    issues.push('No nodes');
        if (this.canvas.elements.size === 0) issues.push('No elements');
        if (this.canvas.supports.size === 0) issues.push('No supports');

        if (issues.length) {
            this.logError('Validation failed: ' + issues.join(', '));
            return false;
        }
        this.log('Structure looks valid — sending to solver');
        return true;
    }

    // ═══ SOLVE ═════════════════════════════════════════════════════════════

    async solve() {
        if (!this.validate()) return;
        this.log('Solving…');
        this.updateStatus('Solving…');

        const payload = {
            nodes:    [...this.canvas.nodes.values()],
            elements: [...this.canvas.elements.values()],
            supports: [...this.canvas.supports.values()],
            loads:    [...this.canvas.loads.values()],
            scale:    CANVAS_SCALE
        };

        try {
            const res = await fetch(`${API}/solve-model`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            const data = await res.json();

            if (!data.success) {
                this.logError('Solver error: ' + data.error);
                this.updateStatus('Solve failed');
                return;
            }

            this.lastResults = data;
            this.log(`Solved — max disp: ${data.summary?.max_displacement_mm?.toFixed(3)}mm, `
                   + `total reaction: ${data.summary?.total_vertical_reaction_kN?.toFixed(2)}kN`);
            this.showResults(data);
            this.renderDiagrams(data);
            this.switchTab('results');
            this.updateStatus('Solved');

        } catch (err) {
            this.logError('Network error: ' + err.message);
            this.updateStatus('Error');
        }
    }

    // ═══ RESULTS DISPLAY ═══════════════════════════════════════════════════

    showResults(data) {
        // Displacements
        const dispDiv = document.getElementById('results-displacements');
        if (data.displacements?.length) {
            let html = '<table class="results-table"><thead><tr><th>Node</th><th>UX (mm)</th><th>UY (mm)</th><th>RZ (rad)</th></tr></thead><tbody>';
            for (const d of data.displacements) {
                html += `<tr><td>${d.node_id}</td><td>${d.ux.toFixed(4)}</td><td>${d.uy.toFixed(4)}</td><td>${d.rz.toFixed(6)}</td></tr>`;
            }
            html += '</tbody></table>';
            dispDiv.innerHTML = html;
        }

        // Reactions
        const reactDiv = document.getElementById('results-reactions');
        if (data.reactions?.length) {
            let html = '<table class="results-table"><thead><tr><th>Node</th><th>Fx (kN)</th><th>Fy (kN)</th><th>Mz (kN·m)</th></tr></thead><tbody>';
            for (const r of data.reactions) {
                html += `<tr><td>${r.node_id}</td><td>${r.fx.toFixed(3)}</td><td>${r.fy.toFixed(3)}</td><td>${r.mz.toFixed(4)}</td></tr>`;
            }
            html += '</tbody></table>';
            reactDiv.innerHTML = html;
        }
    }

    renderDiagrams(data) {
        if (typeof DiagramRenderer !== 'undefined') {
            const canvas = document.getElementById('diagram-canvas');
            const renderer = new DiagramRenderer(canvas);
            const showSFD  = document.getElementById('btn-show-sfd').classList.contains('active');
            const showBMD  = document.getElementById('btn-show-bmd').classList.contains('active');
            renderer.render(data.diagrams || {}, { showSFD, showBMD });
        }
    }

    // ═══ EXPORTS ═══════════════════════════════════════════════════════════

    async exportPDF() {
        if (!this.lastResults) { this.logError('Solve first before exporting PDF'); return; }
        this.log('Generating PDF report…');
        try {
            const payload = {
                filename: 'report.pdf',
                model: {
                    nodes:    [...this.canvas.nodes.values()],
                    elements: [...this.canvas.elements.values()],
                    supports: [...this.canvas.supports.values()],
                    loads:    [...this.canvas.loads.values()],
                    scale:    CANVAS_SCALE
                },
                results: this.lastResults
            };
            const res = await fetch(`${API}/export/pdf`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            if (res.ok) {
                const blob = await res.blob();
                const a = Object.assign(document.createElement('a'),
                    { href: URL.createObjectURL(blob), download: 'report.pdf' });
                a.click();
                this.log('PDF downloaded');
            } else {
                const err = await res.json();
                this.logError('PDF error: ' + err.error);
            }
        } catch (e) { this.logError('PDF export failed: ' + e.message); }
    }

    async exportDXF() {
        if (this.canvas.nodes.size === 0) { this.logError('Model is empty'); return; }
        this.log('Generating DXF…');
        try {
            const payload = {
                filename: 'model.dxf',
                model: {
                    nodes:    [...this.canvas.nodes.values()],
                    elements: [...this.canvas.elements.values()],
                    supports: [...this.canvas.supports.values()],
                    loads:    [...this.canvas.loads.values()],
                    scale:    CANVAS_SCALE
                }
            };
            const res = await fetch(`${API}/export/dxf`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            if (res.ok) {
                const blob = await res.blob();
                const a = Object.assign(document.createElement('a'),
                    { href: URL.createObjectURL(blob), download: 'model.dxf' });
                a.click();
                this.log('DXF downloaded');
            } else {
                const err = await res.json();
                this.logError('DXF error: ' + err.error);
            }
        } catch (e) { this.logError('DXF export failed: ' + e.message); }
    }

    // ═══ AI EXTRACTION ═════════════════════════════════════════════════════

    openAIExtract() {
        document.getElementById('modal-ai-extract').classList.remove('hidden');
    }

    async runAIExtract() {
        const file = document.getElementById('extract-file-input').files[0];
        if (!file) { this.logError('Select an image file first'); return; }

        const status = document.getElementById('extract-status');
        status.textContent = 'Step 1/2 — Analysing image with AI…';

        const form = new FormData();
        form.append('image', file);

        try {
            const res  = await fetch(`${API}/ai/extract`, { method: 'POST', body: form });
            const data = await res.json();

            if (!data.success && data.error) {
                status.textContent = 'Extraction failed: ' + data.error;
                this.logError('AI extract: ' + data.error);
                return;
            }

            const cm = data.extraction?.canvas_model;
            if (!cm) { status.textContent = 'No structure data returned'; return; }

            // Guard: nothing extracted — show helpful message, don't solve
            if (!cm.nodes || cm.nodes.length === 0) {
                status.textContent = '';
                this.logError(
                    'AI could not read the structure from this image. ' +
                    'Make sure the image shows a clear beam diagram with visible ' +
                    'supports, spans/dimensions, and loads. ' +
                    'Text-only pages (instructions, notes) cannot be extracted.'
                );
                return;
            }

            // Load model onto canvas
            this._loadCanvasModel(cm);
            document.getElementById('modal-ai-extract').classList.add('hidden');

            const v = data.extraction?.validation;
            if (v?.issues?.length)   this.logError('AI warnings: ' + v.issues.join('; '));
            if (v?.warnings?.length) this.log('Note: ' + v.warnings.join('; '));

            this.log(`AI extracted: ${cm.nodes.length} nodes, `
                   + `${cm.elements.length} elements, `
                   + `${cm.supports.length} supports, `
                   + `${cm.loads.length} loads`);

            // ── Auto-solve immediately ──────────────────────────────────────
            this.log('Step 2/2 — Solving automatically…');
            await this.solve();

        } catch (e) {
            status.textContent = 'Network error: ' + e.message;
            this.logError('AI extract failed: ' + e.message);
        }
    }

    _loadCanvasModel(cm) {
        this.canvas.nodes.clear(); this.canvas.elements.clear();
        this.canvas.supports.clear(); this.canvas.loads.clear();

        (cm.nodes    || []).forEach(n => this.canvas.nodes.set(n.id, n));
        (cm.elements || []).forEach(e => this.canvas.elements.set(e.id, e));
        (cm.supports || []).forEach(s => this.canvas.supports.set(s.id, s));
        (cm.loads    || []).forEach(l => this.canvas.loads.set(l.id, l));

        this.canvas.fit_view();
        this.updateStatus();
    }

    // ═══ UI HELPERS ════════════════════════════════════════════════════════

    showNodeProperties(node) {
        document.getElementById('properties-content').innerHTML = `
            <table class="prop-table">
                <tr><td>Node ID</td><td><strong>${node.id}</strong></td></tr>
                <tr><td>X</td><td>${(node.x * CANVAS_SCALE).toFixed(0)} mm</td></tr>
                <tr><td>Y</td><td>${(-node.y * CANVAS_SCALE).toFixed(0)} mm</td></tr>
            </table>`;
    }

    showElementProperties(el) {
        document.getElementById('properties-content').innerHTML = `
            <table class="prop-table">
                <tr><td>Element ID</td><td><strong>${el.id}</strong></td></tr>
                <tr><td>Node I</td><td>${el.node_i}</td></tr>
                <tr><td>Node J</td><td>${el.node_j}</td></tr>
                <tr><td>Material</td><td>${el.material}</td></tr>
                <tr><td>Section</td><td>${el.section}</td></tr>
            </table>`;
    }

    clearProperties() {
        document.getElementById('properties-content').innerHTML = '<p class="empty-hint">Nothing selected</p>';
    }

    switchTab(tab) {
        document.querySelectorAll('.panel-tab-content').forEach(el => el.classList.remove('active'));
        document.querySelectorAll('.panel-tab-btn').forEach(el => el.classList.remove('active'));
        document.getElementById(`tab-${tab}`)?.classList.add('active');
        document.querySelector(`[data-tab="${tab}"]`)?.classList.add('active');
    }

    updateStatus(msg = null) {
        const c = this.canvas;
        document.getElementById('status-model').textContent =
            `Nodes: ${c.nodes.size} | Elements: ${c.elements.size} | Supports: ${c.supports.size} | Loads: ${c.loads.size}`;
        if (msg) document.getElementById('status-text').textContent = msg;
    }

    log(msg) {
        const div = document.getElementById('console-output');
        const p = document.createElement('p');
        p.className = 'console-info';
        p.textContent = `[${new Date().toLocaleTimeString()}] ${msg}`;
        div.appendChild(p);
        div.scrollTop = div.scrollHeight;
    }

    logError(msg) {
        const div = document.getElementById('console-output');
        const p = document.createElement('p');
        p.className = 'console-error';
        p.textContent = `[${new Date().toLocaleTimeString()}] ERROR: ${msg}`;
        div.appendChild(p);
        div.scrollTop = div.scrollHeight;
        this.switchTab('console');
    }
}

document.addEventListener('DOMContentLoaded', () => { window.app = new BeamSolverApp(); });
