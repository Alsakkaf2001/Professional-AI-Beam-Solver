"""LemonFox AI client — OpenAI-compatible API + computer-vision image analysis."""
import json
import os
import re
import base64
from typing import Optional
import numpy as np
from PIL import Image, ImageEnhance, ImageOps, ImageFilter
from openai import OpenAI


# ── Extraction prompt ─────────────────────────────────────────────────────────

EXTRACTION_PROMPT = """You are a structural engineering AI assistant.

Based on the structural analysis provided below, return a complete FEM model as STRICT JSON.

Schema:
{
  "nodes":    [{"id":1,"x":0.0,"y":0.0}],
  "elements": [{"id":1,"node_i":1,"node_j":2,"section":"IPE-200","material":"steel"}],
  "supports": [{"node_id":1,"type":"pin"}],
  "loads":    [
    {"type":"point",       "node_id":2,    "magnitude_kN":10.0,"direction":"down"},
    {"type":"distributed", "element_id":1, "magnitude_kN":5.0}
  ]
}

Rules:
- x,y in METRES. x increases left-to-right. y increases upward (0 = ground level).
- Convert: ft×0.3048=m | k/ft×14.5939=kN/m | ton/m×9.81=kN/m | kip×4.4482=kN
- For FRAMES: columns are vertical (x constant, y varies). Beam is horizontal (y constant).
- Distributed loads: one entry per element.
- Support types: "pin"(ux=uy=0) | "fixed"(ux=uy=rz=0) | "roller_y"(uy=0) | "roller_x"(ux=0)
- For portal frames: left base = fixed, right base = pin (unless stated otherwise)
- Load direction: "down","up","left","right"

Return ONLY valid JSON — no markdown, no explanation."""


# ── Computer vision helpers ───────────────────────────────────────────────────

def _ocr_region(img_gray: Image.Image, psm: int = 11) -> str:
    """OCR a PIL grayscale image with enhanced preprocessing."""
    try:
        import pytesseract
        for p in [r'C:\Program Files\Tesseract-OCR\tesseract.exe',
                  r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe']:
            if os.path.exists(p):
                pytesseract.pytesseract.tesseract_cmd = p
                break

        w, h = img_gray.size
        scale = max(1, 2400 // max(w, h, 1))
        big   = img_gray.resize((w * scale, h * scale), Image.LANCZOS)
        enh   = ImageEnhance.Contrast(big).enhance(4.0)
        binary = enh.point(lambda x: 0 if x < 140 else 255)
        return pytesseract.image_to_string(binary, config=f'--psm {psm} --oem 1').strip()
    except Exception:
        return ''


def _multi_ocr(image_path: str) -> dict:
    """
    Run OCR on multiple image regions + the full image.
    Returns { 'full', 'top', 'bottom', 'left', 'right', 'center', 'all' }
    """
    img  = Image.open(image_path)
    w, h = img.size
    gray = img.convert('L')

    regions = {
        'full':   gray,
        'top':    gray.crop((0,      0,      w,     h//3)),
        'bottom': gray.crop((0,      2*h//3, w,     h)),
        'left':   gray.crop((0,      0,      w//3,  h)),
        'right':  gray.crop((2*w//3, 0,      w,     h)),
        'center': gray.crop((w//5,   h//5,   4*w//5, 4*h//5)),
    }

    results = {}
    for name, region in regions.items():
        texts = set()
        for psm in [6, 11, 12]:
            t = _ocr_region(region, psm)
            if t:
                texts.add(t)
        results[name] = ' | '.join(texts)

    results['all'] = ' '.join(results.values())
    return results


def _detect_lines(image_path: str) -> dict:
    """
    Use numpy to find dominant horizontal and vertical lines
    (structural members) in a greyscale image.
    Returns { h_lines: [y,...], v_lines: [x,...], is_frame, n_h, n_v }
    """
    img = Image.open(image_path).convert('L')
    arr = np.array(img, dtype=np.float32)
    w, h = img.size

    # Adaptive dark threshold (lower 30th percentile of pixel values)
    threshold = float(np.percentile(arr, 30))
    dark = arr < threshold                       # True = dark pixel

    # Row density → horizontal lines
    row_dens = dark.mean(axis=1)
    h_raw    = [y for y in range(h) if row_dens[y] > 0.12]

    # Column density → vertical lines
    col_dens = dark.mean(axis=0)
    v_raw    = [x for x in range(w) if col_dens[x] > 0.07]

    def cluster(indices, gap=20):
        if not indices:
            return []
        groups, cur = [], [indices[0]]
        for i in indices[1:]:
            if i - cur[-1] <= gap:
                cur.append(i)
            else:
                groups.append(cur); cur = [i]
        groups.append(cur)
        return [int(np.median(g)) for g in groups]

    h_lines = cluster(h_raw)
    v_lines = cluster(v_raw)

    # A portal frame has ≥2 vertical members and ≥1 horizontal member
    is_frame = len(v_lines) >= 2 and len(h_lines) >= 1

    return {
        'h_lines': h_lines,  'n_h': len(h_lines),
        'v_lines': v_lines,  'n_v': len(v_lines),
        'is_frame': is_frame,
        'image_wh': (w, h),
    }


def _parse_values(text: str) -> dict:
    """
    Extract structural parameters from any OCR text.
    Handles partial OCR (e.g. '18 t' → '18 ft') and various unit formats.
    """
    t = text
    # Fix OCR artefacts
    t = re.sub(r'(\d)\s+[tf]\b',  lambda m: m.group(1) + ' ft', t)
    t = re.sub(r'(\d)ft\b',       r'\1 ft', t)
    t = re.sub(r'(\d)\s*ton/m',   r'\1 ton/m', t, flags=re.I)
    t = re.sub(r'(\d)\s*k/ft\b',  r'\1 k/ft', t, flags=re.I)
    t = re.sub(r'(\d)\s*kn/m\b',  r'\1 kN/m', t, flags=re.I)
    t = re.sub(r'(\d)\s*k\b(?!/)',r'\1 k/ft', t)   # bare 'k' near number

    dims  = re.findall(r'(\d+(?:\.\d+)?)\s*(m|ft|mm)\b', t, re.I)
    loads = re.findall(r'(\d+(?:\.\d+)?)\s*(ton/m|t/m|kN/m|k/ft|kip/ft|kN|k|kip|ton)\b', t, re.I)
    labels= re.findall(r'\b([A-Z])\b', t)
    muls  = re.findall(r'(\d+)\s*[Ii]\b', t)   # "3I", "2I"

    # Detect distributed loads
    is_udl = bool(re.search(r'(\d)\s*(ton/m|kn/m|k/ft|kip/ft|/m|/ft)', t, re.I))
    is_frame   = bool(re.search(r'frame|portal|column', t, re.I))
    is_continuous = bool(re.search(r'continuous', t, re.I))

    # Intermediate supports
    n_int = 0
    m = re.search(r'(\d+)\s+intermediate', t, re.I)
    if m:
        n_int = int(m.group(1))

    return {
        'dims': dims, 'loads': loads, 'labels': labels,
        'muls': muls, 'is_udl': is_udl, 'is_frame': is_frame,
        'is_continuous': is_continuous, 'n_intermediate': n_int,
        'normalised_text': t,
    }


def _to_metres(val: float, unit: str) -> float:
    unit = unit.lower()
    if unit == 'ft':   return round(val * 0.3048, 4)
    if unit == 'mm':   return round(val / 1000,   4)
    if unit == 'cm':   return round(val / 100,    4)
    return round(val, 4)


def _to_kn_per_m(val: float, unit: str) -> float:
    unit = unit.lower()
    if unit in ('ton/m', 't/m'):  return round(val * 9.81,    4)
    if unit in ('k/ft', 'kip/ft'):return round(val * 14.5939, 4)
    return round(val, 4)   # already kN/m


def _build_description(image_path: str) -> str:
    """
    Full description: computer-vision lines + multi-region OCR + parsed values.
    """
    ocr     = _multi_ocr(image_path)
    lines   = _detect_lines(image_path)
    parsed  = _parse_values(ocr['all'])
    w, h    = lines['image_wh']

    desc  = f"=== IMAGE ANALYSIS: {w}x{h}px ===\n\n"

    # ── Structure type ────────────────────────────────────────────────────
    if lines['is_frame'] or parsed['is_frame']:
        n_v = lines['n_v']
        n_h = lines['n_h']
        desc += (
            f"STRUCTURE TYPE: Portal frame detected\n"
            f"  Vertical members (columns): {n_v}\n"
            f"  Horizontal members (beams): {n_h}\n"
            f"  Typical portal frame layout: left column + horizontal beam + right column\n"
            f"  Node layout: A(0,0)=bottom-left  B(span,0)=bottom-right  "
            f"C(0,height)=top-left  D(span,height)=top-right\n"
            f"  Elements: col-left(A->C), beam(C->D), col-right(D->B)\n\n"
        )
    elif parsed['is_continuous']:
        desc += f"STRUCTURE TYPE: Continuous beam, {parsed['n_intermediate']+1} spans\n\n"
    else:
        desc += "STRUCTURE TYPE: Simple beam (assumed if unclear)\n\n"

    # ── Dimensions ────────────────────────────────────────────────────────
    all_dims = parsed['dims']
    if all_dims:
        # Sort by value: smaller → height, larger → span (heuristic for frames)
        metres = [(_to_metres(float(v), u), v, u) for v, u in all_dims]
        metres.sort(key=lambda x: x[0])
        if lines['is_frame'] or parsed['is_frame']:
            if len(metres) >= 2:
                height_m = metres[0][0]
                span_m   = metres[-1][0]
                desc += f"DIMENSIONS (from OCR):\n"
                desc += f"  Span  (x-direction): {span_m} m  [{metres[-1][1]} {metres[-1][2]}]\n"
                desc += f"  Height(y-direction): {height_m} m  [{metres[0][1]} {metres[0][2]}]\n"
                desc += (
                    f"  Node coordinates:\n"
                    f"    A=(0, 0)  B=({span_m}, 0)  C=(0, {height_m})  D=({span_m}, {height_m})\n\n"
                )
            elif len(metres) == 1:
                desc += f"  One dimension found: {metres[0][0]} m — assumed span\n\n"
        else:
            # Beam: accumulate spans
            span_ms = [m[0] for m in metres]
            x_coords = [round(sum(span_ms[:i]), 4) for i in range(len(span_ms)+1)]
            desc += f"SPAN DIMENSIONS: {span_ms} m\nNode x-coords: {x_coords}\n\n"
    else:
        desc += "DIMENSIONS: None detected by OCR\n\n"

    # ── Loads ─────────────────────────────────────────────────────────────
    if parsed['loads']:
        desc += "LOADS:\n"
        for val, unit in parsed['loads']:
            v = float(val)
            if '/' in unit.lower() or unit.lower() in ('ton/m', 't/m'):
                kn = _to_kn_per_m(v, unit)
                desc += f"  Distributed load: {val} {unit} = {kn} kN/m\n"
                desc += f"  Apply to: horizontal beam element(s)\n"
            else:
                kn = v * 4.4482 if unit.lower() in ('k', 'kip') else v
                desc += f"  Point load: {val} {unit} = {kn:.2f} kN\n"
        desc += "\n"
    else:
        desc += "LOADS: None detected\n\n"

    # ── OCR raw (by region) ───────────────────────────────────────────────
    desc += "OCR TEXT BY REGION:\n"
    for region in ('top', 'right', 'bottom', 'left'):
        if ocr.get(region, '').strip():
            desc += f"  {region.upper()}: {ocr[region][:200]}\n"

    # ── Section multipliers ───────────────────────────────────────────────
    if parsed['muls']:
        desc += f"\nSECTION MULTIPLIERS FOUND: {parsed['muls']}I\n"
        desc += "  (Use IPE-300 for higher-I beam, IPE-200 for columns)\n"

    desc += "\nIMPORTANT INSTRUCTIONS:\n"
    if lines['is_frame'] or parsed['is_frame']:
        desc += (
            "  - This is a PORTAL FRAME. You MUST generate 4 nodes and 3 elements.\n"
            "  - Left base support (A) = 'fixed', right base (B) = 'pin'\n"
            "  - Distributed load goes on the BEAM element only (element C->D)\n"
            "  - Column elements have NO loads\n"
            "  - Columns are VERTICAL: x is constant, y varies\n"
        )
    return desc


# ── LemonFox client ───────────────────────────────────────────────────────────

class LemonFoxClient:
    def __init__(self, api_key: Optional[str] = None):
        key = api_key or os.getenv('LEMONFOX_API_KEY')
        if not key:
            raise ValueError("LemonFox API key not found. Set LEMONFOX_API_KEY.")
        self.client = OpenAI(api_key=key, base_url="https://api.lemonfox.ai/v1")
        self.model  = 'llama-70b-chat'

    def _extract_json(self, text: str) -> str:
        text = text.strip()
        fence = re.search(r'```(?:json)?\s*([\s\S]*?)```', text, re.IGNORECASE)
        if fence:
            text = fence.group(1).strip()
        try:
            json.loads(text); return text
        except json.JSONDecodeError:
            pass
        for oc, cc in [('{', '}'), ('[', ']')]:
            s = text.find(oc)
            if s == -1: continue
            depth = 0; in_str = False; esc = False
            for i, ch in enumerate(text[s:], s):
                if esc:                   esc = False; continue
                if ch == '\\' and in_str: esc = True;  continue
                if ch == '"':             in_str = not in_str; continue
                if in_str:                continue
                if ch == oc:              depth += 1
                elif ch == cc:
                    depth -= 1
                    if depth == 0:
                        return text[s:i+1]
        raise ValueError(f"No JSON in response.\nRaw (400 chars):\n{text[:400]}")

    def _parse_json(self, text: str) -> dict:
        return json.loads(self._extract_json(text))

    def _image_to_base64(self, image_path: str):
        ext  = image_path.rsplit('.', 1)[-1].lower()
        mime = {'jpg':'image/jpeg','jpeg':'image/jpeg','png':'image/png',
                'gif':'image/gif','webp':'image/webp'}.get(ext,'image/jpeg')
        with open(image_path, 'rb') as f:
            return base64.b64encode(f.read()).decode(), mime

    def _call_llm(self, prompt: str) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system",
                 "content": "You are a structural engineering assistant. Return only valid JSON."},
                {"role": "user", "content": prompt}
            ]
        )
        return response.choices[0].message.content

    # ── Public API ────────────────────────────────────────────────────────

    def analyze_image(self, image_path: str, prompt: str) -> str:
        """Vision attempt first, then CV+OCR fallback."""
        b64, mime = self._image_to_base64(image_path)
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": [
                    {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
                    {"type": "text",      "text": prompt}
                ]}]
            )
            return response.choices[0].message.content
        except Exception:
            pass

        # CV + OCR fallback
        description = _build_description(image_path)
        return self._call_llm(
            f"A structural engineering drawing was analysed with computer vision and OCR.\n"
            f"Here is everything extracted:\n\n{description}\n\n{prompt}"
        )

    def extract_structure_from_image(self, image_path: str) -> dict:
        raw = self.analyze_image(image_path, EXTRACTION_PROMPT)
        try:
            result = self._parse_json(raw)
        except (json.JSONDecodeError, ValueError) as e:
            raise ValueError(f"LemonFox non-JSON output.\nError: {e}\nRaw: {raw[:400]}")

        # Retry if empty
        if not result.get('nodes'):
            desc = _build_description(image_path)
            retry = (
                f"Computer vision extracted this from the structural image:\n\n{desc}\n\n"
                f"Generate a complete FEM model. If some dimensions are unclear, make "
                f"reasonable engineering assumptions.\n\n{EXTRACTION_PROMPT}"
            )
            try:
                result = self._parse_json(self._call_llm(retry))
            except Exception:
                pass

        # Override node coordinates with OCR geometry (more reliable than LLM guesses)
        self._apply_ocr_geometry(image_path, result)
        return result

    def _apply_ocr_geometry(self, image_path: str, result: dict):
        """
        Replace LLM-guessed node coordinates with OCR-computed ones when possible.
        """
        ocr    = _multi_ocr(image_path)
        parsed = _parse_values(ocr['all'])
        lines  = _detect_lines(image_path)
        nodes  = result.get('nodes', [])

        if not nodes:
            return

        is_frame = lines['is_frame'] or parsed['is_frame']
        dims_m   = [_to_metres(float(v), u) for v, u in parsed['dims']]
        dims_m.sort()

        if is_frame and len(nodes) == 4 and len(dims_m) >= 2:
            span_m   = dims_m[-1]
            height_m = dims_m[0]
            # Assign canonical portal frame coordinates
            # A=node1(0,0), B=node2(span,0), C=node3(0,height), D=node4(span,height)
            coords = [(0, 0), (span_m, 0), (0, height_m), (span_m, height_m)]
            for node, (x, y) in zip(nodes, coords):
                node['x'] = x; node['y'] = y

        elif not is_frame and len(dims_m) >= 1:
            # Beam: correct truncated OCR spans
            spans = list(dims_m)
            if len(spans) > 1:
                avg = sum(spans) / len(spans)
                spans = [s * 3 if s < 0.4 * avg else s for s in spans]
            x_coords = [round(sum(spans[:i]), 4) for i in range(len(spans)+1)]
            if len(x_coords) == len(nodes):
                for node, x in zip(nodes, x_coords):
                    node['x'] = x; node['y'] = 0.0

    def repair_structural_data(self, structure_data: dict) -> dict:
        prompt = f"""Structural engineer reviewing FEM data. Check and repair:
1. All node_i/node_j in elements must reference valid node IDs
2. Total constrained DOF >= 3
3. Distributed loads: one entry PER element

Input:
{json.dumps(structure_data, indent=2)}

Return STRICT JSON only — same schema plus "repairs" array."""
        try:
            result = self._parse_json(self._call_llm(prompt))
            result.setdefault('repairs', [])
            return result
        except Exception:
            structure_data.setdefault('repairs', [])
            return structure_data
