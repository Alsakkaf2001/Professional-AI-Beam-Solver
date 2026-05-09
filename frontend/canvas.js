/**
 * Canvas drawing and rendering engine
 */

class Canvas {
    constructor(canvasElement) {
        this.canvas = canvasElement;
        this.ctx = canvasElement.getContext('2d');
        this.width = canvasElement.width;
        this.height = canvasElement.height;
        
        // View transform
        this.pan = { x: 0, y: 0 };
        this.zoom = 1.0;
        this.gridSize = 20;
        
        // Structural elements
        this.nodes = new Map();
        this.elements = new Map();
        this.supports = new Map();
        this.loads = new Map();
        
        // Selection
        this.selectedNodeId = null;
        this.selectedElementId = null;
        this.selectedSupportId = null;
        this.selectedLoadId = null;
        
        // Styles
        this.styles = {
            node: { radius: 5, fill: '#0078d4', stroke: '#ffffff', width: 2 },
            element: { stroke: '#107c10', width: 2 },
            support: { size: 20, fill: '#d13438' },
            load: { arrow: { length: 30, width: 15, color: '#ffb900' } },
            grid: { stroke: '#343434', width: 0.5 },
            selection: { stroke: '#0078d4', width: 2, dash: 5 }
        };
        
        this.resize();
        window.addEventListener('resize', () => this.resize());
    }
    
    resize() {
        const rect = this.canvas.getBoundingClientRect();
        this.canvas.width = rect.width;
        this.canvas.height = rect.height;
        this.width = rect.width;
        this.height = rect.height;
        this.draw();
    }
    
    // ================ COORDINATE TRANSFORMS ================
    
    worldToScreen(x, y) {
        const sx = (x - this.pan.x) * this.zoom + this.width / 2;
        const sy = (y - this.pan.y) * this.zoom + this.height / 2;
        return { x: sx, y: sy };
    }
    
    screenToWorld(sx, sy) {
        const x = (sx - this.width / 2) / this.zoom + this.pan.x;
        const y = (sy - this.height / 2) / this.zoom + this.pan.y;
        return { x, y };
    }
    
    // ================ DRAWING PRIMITIVES ================
    
    drawNode(node, selected = false) {
        const { x: sx, y: sy } = this.worldToScreen(node.x, node.y);
        const radius = this.styles.node.radius;
        
        // Fill
        this.ctx.fillStyle = selected ? '#ff8c00' : this.styles.node.fill;
        this.ctx.beginPath();
        this.ctx.arc(sx, sy, radius, 0, Math.PI * 2);
        this.ctx.fill();
        
        // Stroke
        this.ctx.strokeStyle = this.styles.node.stroke;
        this.ctx.lineWidth = this.styles.node.width;
        this.ctx.stroke();
        
        // Label
        if (this.zoom > 0.5) {
            this.ctx.fillStyle = '#ffffff';
            this.ctx.font = '10px Arial';
            this.ctx.textAlign = 'center';
            this.ctx.fillText(`N${node.id}`, sx, sy - 15);
        }
    }
    
    drawElement(element, selected = false) {
        const node_i = this.nodes.get(element.node_i);
        const node_j = this.nodes.get(element.node_j);
        
        if (!node_i || !node_j) return;
        
        const p1 = this.worldToScreen(node_i.x, node_i.y);
        const p2 = this.worldToScreen(node_j.x, node_j.y);
        
        // Line
        this.ctx.strokeStyle = selected ? '#ff8c00' : this.styles.element.stroke;
        this.ctx.lineWidth = selected ? 3 : this.styles.element.width;
        this.ctx.beginPath();
        this.ctx.moveTo(p1.x, p1.y);
        this.ctx.lineTo(p2.x, p2.y);
        this.ctx.stroke();
        
        // Label
        if (this.zoom > 0.5) {
            const mx = (p1.x + p2.x) / 2;
            const my = (p1.y + p2.y) / 2;
            this.ctx.fillStyle = '#ffffff';
            this.ctx.font = 'bold 10px Arial';
            this.ctx.textAlign = 'center';
            this.ctx.fillText(`E${element.id}`, mx, my - 10);
        }
    }
    
    drawSupport(support) {
        const node = this.nodes.get(support.node_id);
        if (!node) return;
        
        const { x: sx, y: sy } = this.worldToScreen(node.x, node.y);
        const size = this.styles.support.size * Math.sqrt(this.zoom);
        
        this.ctx.fillStyle = this.styles.support.fill;
        this.ctx.strokeStyle = '#ffffff';
        this.ctx.lineWidth = 1;
        
        switch (support.type) {
            case 'pin':
                // Triangle
                this.ctx.beginPath();
                this.ctx.moveTo(sx - size/2, sy);
                this.ctx.lineTo(sx + size/2, sy);
                this.ctx.lineTo(sx, sy - size);
                this.ctx.closePath();
                this.ctx.fill();
                this.ctx.stroke();
                
                // Hatch
                for (let i = 0; i < 3; i++) {
                    const x1 = sx - size/2 + i * size/3;
                    const y1 = sy;
                    this.ctx.strokeStyle = this.styles.support.fill;
                    this.ctx.beginPath();
                    this.ctx.moveTo(x1, y1);
                    this.ctx.lineTo(x1 + size/4, y1 + size/4);
                    this.ctx.stroke();
                }
                break;
            
            case 'fixed':
                // Rectangle
                this.ctx.fillRect(sx - size/2, sy - size/2, size, size);
                this.ctx.strokeRect(sx - size/2, sy - size/2, size, size);
                break;
            
            case 'roller_x':
                // Circle with horizontal arrow
                this.ctx.beginPath();
                this.ctx.arc(sx, sy, size/2, 0, Math.PI * 2);
                this.ctx.fill();
                this.ctx.stroke();
                
                // Arrow
                this.drawArrow(sx - size, sy, sx - size/2, sy, 8);
                break;
            
            case 'roller_y':
                // Circle with vertical arrow
                this.ctx.beginPath();
                this.ctx.arc(sx, sy, size/2, 0, Math.PI * 2);
                this.ctx.fill();
                this.ctx.stroke();
                
                // Arrow
                this.drawArrow(sx, sy - size, sx, sy - size/2, 8);
                break;
        }
    }
    
    drawLoad(load) {
        this.ctx.strokeStyle = this.styles.load.arrow.color;
        this.ctx.fillStyle   = this.styles.load.arrow.color;
        this.ctx.lineWidth   = 2;

        if (load.type === 'point') {
            const node = this.nodes.get(load.node_id);
            if (!node) return;
            const { x: sx, y: sy } = this.worldToScreen(node.x, node.y);
            const arrowLen = Math.max(25, Math.min(50, Math.abs(load.value) * 3)) * Math.sqrt(this.zoom);
            // Positive value = downward force → arrow points down (sy + arrowLen)
            this.drawArrow(sx, sy - arrowLen, sx, sy, 10);
            this.ctx.fillStyle = '#ffb900';
            this.ctx.font = `${Math.max(9, 11 * this.zoom)}px monospace`;
            this.ctx.textAlign = 'left';
            this.ctx.fillText(`${load.value.toFixed(1)}kN`, sx + 8, sy - arrowLen / 2);

        } else if (load.type === 'distributed') {
            const elem = this.elements.get(load.element_id);
            if (!elem) return;
            const ni = this.nodes.get(elem.node_i);
            const nj = this.nodes.get(elem.node_j);
            if (!ni || !nj) return;

            const p1 = this.worldToScreen(ni.x, ni.y);
            const p2 = this.worldToScreen(nj.x, nj.y);
            const nArrows = 5;
            const arrowLen = 18 * Math.sqrt(this.zoom);

            for (let t = 0; t <= 1; t += 1 / nArrows) {
                const ax = p1.x + t * (p2.x - p1.x);
                const ay = p1.y + t * (p2.y - p1.y);
                this.drawArrow(ax, ay - arrowLen, ax, ay, 6);
            }
            // Horizontal line at top of arrows
            const lx1 = p1.x; const ly1 = p1.y - arrowLen;
            const lx2 = p2.x; const ly2 = p2.y - arrowLen;
            this.ctx.beginPath();
            this.ctx.moveTo(lx1, ly1); this.ctx.lineTo(lx2, ly2);
            this.ctx.strokeStyle = '#ffb900'; this.ctx.lineWidth = 2;
            this.ctx.stroke();

            // Label at midpoint
            const mx = (lx1 + lx2) / 2, my = (ly1 + ly2) / 2;
            this.ctx.fillStyle = '#ffb900';
            this.ctx.font = `${Math.max(9, 11 * this.zoom)}px monospace`;
            this.ctx.textAlign = 'center';
            this.ctx.fillText(`${load.value.toFixed(1)}kN/m`, mx, my - 6);
        }
    }
    
    drawArrow(fromX, fromY, toX, toY, headlen) {
        const angle = Math.atan2(toY - fromY, toX - fromX);
        
        // Line
        this.ctx.beginPath();
        this.ctx.moveTo(fromX, fromY);
        this.ctx.lineTo(toX, toY);
        this.ctx.stroke();
        
        // Arrowhead
        this.ctx.beginPath();
        this.ctx.moveTo(toX, toY);
        this.ctx.lineTo(toX - headlen * Math.cos(angle - Math.PI / 6), toY - headlen * Math.sin(angle - Math.PI / 6));
        this.ctx.lineTo(toX - headlen * Math.cos(angle + Math.PI / 6), toY - headlen * Math.sin(angle + Math.PI / 6));
        this.ctx.closePath();
        this.ctx.fill();
    }
    
    // ================ GRID AND BACKGROUND ================
    
    drawGrid() {
        const gridSpacing = this.gridSize * this.zoom;
        
        if (gridSpacing < 2) return;
        
        this.ctx.strokeStyle = this.styles.grid.stroke;
        this.ctx.lineWidth = this.styles.grid.width;
        
        // Vertical lines
        const startX = Math.floor((this.pan.x - this.width / (2 * this.zoom)) / this.gridSize) * this.gridSize;
        const endX = Math.ceil((this.pan.x + this.width / (2 * this.zoom)) / this.gridSize) * this.gridSize;
        
        for (let x = startX; x <= endX; x += this.gridSize) {
            const sx = this.worldToScreen(x, 0).x;
            this.ctx.beginPath();
            this.ctx.moveTo(sx, 0);
            this.ctx.lineTo(sx, this.height);
            this.ctx.stroke();
        }
        
        // Horizontal lines
        const startY = Math.floor((this.pan.y - this.height / (2 * this.zoom)) / this.gridSize) * this.gridSize;
        const endY = Math.ceil((this.pan.y + this.height / (2 * this.zoom)) / this.gridSize) * this.gridSize;
        
        for (let y = startY; y <= endY; y += this.gridSize) {
            const sy = this.worldToScreen(0, y).y;
            this.ctx.beginPath();
            this.ctx.moveTo(0, sy);
            this.ctx.lineTo(this.width, sy);
            this.ctx.stroke();
        }
    }
    
    // ================ MAIN RENDER ================
    
    draw() {
        // Clear
        this.ctx.fillStyle = '#0a0a0a';
        this.ctx.fillRect(0, 0, this.width, this.height);
        
        // Save context
        this.ctx.save();
        
        // Draw grid
        this.drawGrid();
        
        // Draw elements
        for (const [id, element] of this.elements) {
            this.drawElement(element, id === this.selectedElementId);
        }
        
        // Draw supports
        for (const [id, support] of this.supports) {
            this.drawSupport(support);
        }
        
        // Draw loads
        for (const [id, load] of this.loads) {
            this.drawLoad(load);
        }
        
        // Draw nodes (on top)
        for (const [id, node] of this.nodes) {
            this.drawNode(node, id === this.selectedNodeId);
        }
        
        this.ctx.restore();
    }
    
    // ================ INTERACTION ================
    
    getElementAt(sx, sy) {
        const tolerance = 10;
        const { x: wx, y: wy } = this.screenToWorld(sx, sy);
        
        // Check nodes
        for (const [id, node] of this.nodes) {
            if (Math.hypot(node.x - wx, node.y - wy) < tolerance / this.zoom) {
                return { type: 'node', id, obj: node };
            }
        }
        
        // Check elements
        for (const [id, element] of this.elements) {
            const node_i = this.nodes.get(element.node_i);
            const node_j = this.nodes.get(element.node_j);
            if (!node_i || !node_j) continue;
            
            const dist = this.distancePointToLineSegment(
                wx, wy,
                node_i.x, node_i.y,
                node_j.x, node_j.y
            );
            
            if (dist < tolerance / this.zoom) {
                return { type: 'element', id, obj: element };
            }
        }
        
        return null;
    }
    
    distancePointToLineSegment(px, py, x1, y1, x2, y2) {
        const A = px - x1;
        const B = py - y1;
        const C = x2 - x1;
        const D = y2 - y1;
        
        const dot = A * C + B * D;
        const lenSq = C * C + D * D;
        let param = -1;
        
        if (lenSq !== 0) param = dot / lenSq;
        
        let xx, yy;
        
        if (param < 0) {
            xx = x1;
            yy = y1;
        } else if (param > 1) {
            xx = x2;
            yy = y2;
        } else {
            xx = x1 + param * C;
            yy = y1 + param * D;
        }
        
        const dx = px - xx;
        const dy = py - yy;
        return Math.hypot(dx, dy);
    }
    
    // ================ VIEW CONTROL ================
    
    zoom_in() {
        this.zoom *= 1.2;
        this.draw();
    }
    
    zoom_out() {
        this.zoom /= 1.2;
        this.draw();
    }
    
    fit_view() {
        if (this.nodes.size === 0) return;
        
        // Find bounds
        let minX = Infinity, maxX = -Infinity;
        let minY = Infinity, maxY = -Infinity;
        
        for (const node of this.nodes.values()) {
            minX = Math.min(minX, node.x);
            maxX = Math.max(maxX, node.x);
            minY = Math.min(minY, node.y);
            maxY = Math.max(maxY, node.y);
        }
        
        const padding = 100;
        const centerX = (minX + maxX) / 2;
        const centerY = (minY + maxY) / 2;
        
        const width = maxX - minX + padding * 2;
        const height = maxY - minY + padding * 2;
        
        this.zoom = Math.min(this.width / width, this.height / height);
        this.pan = { x: centerX, y: centerY };
        this.draw();
    }
    
    pan_view(dx, dy) {
        this.pan.x -= dx / this.zoom;
        this.pan.y -= dy / this.zoom;
        this.draw();
    }
}
