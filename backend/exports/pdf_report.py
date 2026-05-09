"""PDF report generation — accepts plain dict model + results."""
import io
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer,
                                 Table, TableStyle, PageBreak)
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def _diagrams_image(diagrams: dict) -> bytes | None:
    if not diagrams:
        return None
    try:
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 7))

        for key, d in diagrams.items():
            x = d.get('x_global', [])
            sfd = d.get('shear_forces', [])
            bmd = d.get('bending_moments', [])
            label = f"E{d.get('element_id', key)}"
            if x and sfd:
                ax1.plot(x, sfd, label=label)
            if x and bmd:
                ax2.plot(x, bmd, label=label)

        ax1.axhline(0, color='k', linewidth=0.5)
        ax1.set_ylabel('Shear Force (kN)')
        ax1.set_title('Shear Force Diagram')
        ax1.grid(True, alpha=0.3)
        ax1.legend(fontsize=8)

        ax2.axhline(0, color='k', linewidth=0.5)
        ax2.set_ylabel('Bending Moment (kN·m)')
        ax2.set_title('Bending Moment Diagram')
        ax2.grid(True, alpha=0.3)
        ax2.legend(fontsize=8)

        plt.tight_layout()
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=120, bbox_inches='tight')
        buf.seek(0)
        plt.close()
        return buf
    except Exception:
        return None


def generate_pdf_report(model_data: dict, results_data: dict, filepath: str):
    """Generate PDF from plain-dict model and results."""
    model_data   = model_data or {}
    results_data = results_data or {}

    styles = getSampleStyleSheet()

    doc = SimpleDocTemplate(filepath, pagesize=A4,
                            leftMargin=0.75*inch, rightMargin=0.75*inch,
                            topMargin=0.75*inch, bottomMargin=0.75*inch)
    elems = []

    # ── title ──
    title_style = ParagraphStyle('RPTitle', parent=styles['Title'],
                                 fontSize=20, textColor=colors.HexColor('#1a3a52'),
                                 spaceAfter=20, alignment=1)
    elems.append(Paragraph('Structural Analysis Report', title_style))
    elems.append(Paragraph(datetime.now().strftime('%Y-%m-%d %H:%M'), styles['Normal']))
    elems.append(Spacer(1, 0.3*inch))

    # ── summary ──
    nodes    = model_data.get('nodes', [])
    elements = model_data.get('elements', [])
    supports = model_data.get('supports', [])
    loads    = model_data.get('loads', [])

    summary_data = [
        ['Property', 'Value'],
        ['Nodes',       str(len(nodes))],
        ['Elements',    str(len(elements))],
        ['Supports',    str(len(supports))],
        ['Loads',       str(len(loads))],
    ]
    t = Table(summary_data, colWidths=[2.5*inch, 2*inch])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c5aa0')),
        ('TEXTCOLOR',  (0, 0), (-1, 0), colors.white),
        ('FONTNAME',   (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('GRID',       (0, 0), (-1, -1), 0.5, colors.black),
        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f0f4ff')),
    ]))
    elems.append(Paragraph('Project Summary', styles['Heading2']))
    elems.append(t)
    elems.append(Spacer(1, 0.25*inch))

    # ── reactions ──
    reactions = results_data.get('reactions', [])
    if reactions:
        react_data = [['Node', 'Fx (kN)', 'Fy (kN)', 'Mz (kN·m)']]
        for r in reactions:
            react_data.append([str(r['node_id']),
                                f"{r['fx']:.3f}", f"{r['fy']:.3f}", f"{r['mz']:.3f}"])
        rt = Table(react_data, colWidths=[1.2*inch, 1.5*inch, 1.5*inch, 1.5*inch])
        rt.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c5aa0')),
            ('TEXTCOLOR',  (0, 0), (-1, 0), colors.white),
            ('FONTNAME',   (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('ALIGN',      (1, 0), (-1, -1), 'CENTER'),
            ('GRID',       (0, 0), (-1, -1), 0.5, colors.black),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f9f9f9')),
        ]))
        elems.append(Paragraph('Support Reactions', styles['Heading2']))
        elems.append(rt)
        elems.append(Spacer(1, 0.25*inch))

    # ── displacements ──
    displacements = results_data.get('displacements', [])
    if displacements:
        disp_data = [['Node', 'UX (mm)', 'UY (mm)', 'RZ (rad)']]
        for d in displacements:
            disp_data.append([str(d['node_id']),
                               f"{d['ux']:.4f}", f"{d['uy']:.4f}", f"{d['rz']:.6f}"])
        dt = Table(disp_data, colWidths=[1.2*inch, 1.5*inch, 1.5*inch, 1.5*inch])
        dt.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c5aa0')),
            ('TEXTCOLOR',  (0, 0), (-1, 0), colors.white),
            ('FONTNAME',   (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('ALIGN',      (1, 0), (-1, -1), 'CENTER'),
            ('GRID',       (0, 0), (-1, -1), 0.5, colors.black),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f9f9f9')),
        ]))
        elems.append(Paragraph('Node Displacements', styles['Heading2']))
        elems.append(dt)
        elems.append(Spacer(1, 0.25*inch))

    # ── diagrams image ──
    diagrams = results_data.get('diagrams', {})
    img_buf = _diagrams_image(diagrams)
    if img_buf:
        from reportlab.platypus import Image as RLImage
        elems.append(Paragraph('Internal Force Diagrams', styles['Heading2']))
        elems.append(RLImage(img_buf, width=6*inch, height=4*inch))

    doc.build(elems)
