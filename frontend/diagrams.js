/**
 * SFD / BMD diagram renderer on a canvas element.
 */

class DiagramRenderer {
    constructor(canvasEl) {
        this.canvas = canvasEl;
        this.ctx    = canvasEl.getContext('2d');
        this._resize();
    }

    _resize() {
        const r = this.canvas.getBoundingClientRect();
        this.canvas.width  = r.width  || 300;
        this.canvas.height = r.height || 200;
        this.W = this.canvas.width;
        this.H = this.canvas.height;
    }

    render(diagrams, opts = {}) {
        this._resize();
        const { showSFD = true, showBMD = true } = opts;
        const ctx = this.ctx;

        ctx.fillStyle = '#0d0d0d';
        ctx.fillRect(0, 0, this.W, this.H);

        const keys = Object.keys(diagrams);
        if (!keys.length) {
            ctx.fillStyle = '#555';
            ctx.font = '13px monospace';
            ctx.textAlign = 'center';
            ctx.fillText('No diagram data', this.W / 2, this.H / 2);
            return;
        }

        // Collect all x and values
        let allX = [], allSFD = [], allBMD = [];
        for (const key of keys) {
            const d = diagrams[key];
            allX   = allX.concat(d.x_global || []);
            allSFD = allSFD.concat(d.shear_forces    || []);
            allBMD = allBMD.concat(d.bending_moments || []);
        }

        const minX = Math.min(...allX), maxX = Math.max(...allX);
        const spanX = maxX - minX || 1;

        const rows = (showSFD && showBMD) ? 2 : 1;
        const rowH = this.H / rows;
        const pad  = { l: 50, r: 10, t: 24, b: 24 };

        const drawRow = (values, label, color, rowIdx) => {
            const yOff = rowIdx * rowH;
            const maxAbs = Math.max(...values.map(Math.abs), 1e-9);
            const scale  = (rowH - pad.t - pad.b) / 2 / maxAbs;
            const baseline = yOff + pad.t + (rowH - pad.t - pad.b) / 2;

            // baseline
            ctx.strokeStyle = '#444'; ctx.lineWidth = 0.5;
            ctx.beginPath();
            const bx0 = pad.l, bx1 = this.W - pad.r;
            ctx.moveTo(bx0, baseline); ctx.lineTo(bx1, baseline);
            ctx.stroke();

            // axis labels
            ctx.fillStyle = '#888'; ctx.font = '10px monospace'; ctx.textAlign = 'left';
            ctx.fillText(label, 4, yOff + pad.t + 10);
            ctx.fillStyle = '#555'; ctx.textAlign = 'right';
            ctx.fillText(`+${maxAbs.toFixed(2)}`, pad.l - 2, yOff + pad.t + 4);
            ctx.fillText(`-${maxAbs.toFixed(2)}`, pad.l - 2, yOff + rowH - pad.b);

            // fill + stroke for each element
            for (const key of keys) {
                const d   = diagrams[key];
                const xs  = d.x_global || [];
                const vs  = label.startsWith('SFD') ? d.shear_forces : d.bending_moments;
                if (!xs.length || !vs?.length) continue;

                ctx.beginPath();
                ctx.moveTo(this._mapX(xs[0], minX, spanX, pad), baseline);

                for (let i = 0; i < xs.length; i++) {
                    const sx = this._mapX(xs[i], minX, spanX, pad);
                    const sy = baseline - vs[i] * scale;
                    ctx.lineTo(sx, sy);
                }
                ctx.lineTo(this._mapX(xs[xs.length - 1], minX, spanX, pad), baseline);
                ctx.closePath();

                ctx.fillStyle = color + '33';
                ctx.fill();

                ctx.beginPath();
                for (let i = 0; i < xs.length; i++) {
                    const sx = this._mapX(xs[i], minX, spanX, pad);
                    const sy = baseline - vs[i] * scale;
                    i === 0 ? ctx.moveTo(sx, sy) : ctx.lineTo(sx, sy);
                }
                ctx.strokeStyle = color; ctx.lineWidth = 1.5;
                ctx.stroke();
            }

            // zero label
            ctx.fillStyle = '#666'; ctx.font = '9px monospace'; ctx.textAlign = 'right';
            ctx.fillText('0', pad.l - 2, baseline + 4);
        };

        let row = 0;
        if (showSFD) { drawRow(allSFD, 'SFD (kN)',    '#4fc3f7', row); row++; }
        if (showBMD) { drawRow(allBMD, 'BMD (kN·m)',  '#f48fb1', row); }
    }

    _mapX(x, minX, spanX, pad) {
        return pad.l + ((x - minX) / spanX) * (this.W - pad.l - pad.r);
    }
}
