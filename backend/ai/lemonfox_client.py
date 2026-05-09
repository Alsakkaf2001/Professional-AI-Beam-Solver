"""LemonFox AI client (OpenAI-compatible API) with OCR image analysis."""
import json
import os
import re
import base64
from typing import Optional
from openai import OpenAI
from PIL import Image, ImageFilter, ImageOps


EXTRACTION_PROMPT = """You are a structural engineering AI assistant.

Based on the structural drawing information provided, extract the FEM model.

Return STRICT JSON only. No markdown. No explanation. No comments.

Use this exact schema:
{
  "nodes": [{"id": 1, "x": 0.0, "y": 0.0}],
  "elements": [{"id": 1, "node_i": 1, "node_j": 2}],
  "supports": [{"node_id": 1, "type": "pin"}],
  "loads": [
    {"type": "point",       "node_id": 2,    "magnitude_kN": 10.0, "direction": "down"},
    {"type": "distributed", "element_id": 1, "magnitude_kN": 5.0}
  ]
}

Rules:
- x increases left to right in METRES (convert ft->m: multiply by 0.3048)
- y = 0 for all nodes on a horizontal beam
- Convert k/ft -> kN/m by multiplying by 14.5939
- Convert kips (k) -> kN by multiplying by 4.4482
- Distributed loads apply to each element separately (one entry per element)
- Support types: "pin", "fixed", "roller_x", "roller_y"
- Load directions: "down", "up", "left", "right"

Only return valid JSON — nothing else."""


def _ocr_image(image_path: str) -> str:
    """Extract text from image using pytesseract if available."""
    try:
        import pytesseract
        # Common Windows install path
        tess_paths = [
            r'C:\Program Files\Tesseract-OCR\tesseract.exe',
            r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe',
        ]
        for p in tess_paths:
            if os.path.exists(p):
                pytesseract.pytesseract.tesseract_cmd = p
                break

        img = Image.open(image_path).convert('L')
        # Enhance contrast for better OCR
        img = ImageOps.autocontrast(img)
        text = pytesseract.image_to_string(img, config='--psm 6')
        return text.strip()
    except Exception:
        return ''


def _build_text_description(image_path: str) -> str:
    """Build a text description of the structural image using PIL + OCR."""
    img   = Image.open(image_path)
    w, h  = img.size
    ratio = round(w / h, 2)

    raw_ocr = _ocr_image(image_path)

    # ── normalise common OCR mistakes ─────────────────────────────────────
    ocr = raw_ocr
    # "18 t" / "18 f" / "18ft" -> "18 ft"
    ocr = re.sub(r'(\d+)\s+[tf]\b', lambda m: m.group(1) + ' ft', ocr)
    ocr = re.sub(r'(\d+)ft\b', r'\1 ft', ocr)
    # "2k" / "2 k" before /ft context -> "2 k/ft"
    ocr = re.sub(r'(\d+(?:\.\d+)?)\s*k\b(?!/)', r'\1 k/ft', ocr)

    # ── extract structured info ───────────────────────────────────────────
    spans = re.findall(r'(\d+(?:\.\d+)?)\s*(ft|m|mm)\b', ocr, re.IGNORECASE)

    loads_found = re.findall(
        r'(\d+(?:\.\d+)?)\s*(k/ft|kip/ft|kN/m|kN|k|kip|kips)\b',
        ocr, re.IGNORECASE
    )

    labels = re.findall(r'\b([A-Z])\b', ocr)

    # ── infer node count from "intermediate supports" ─────────────────────
    n_intermediate = 0
    m = re.search(r'(\d+)\s+intermediate', ocr, re.IGNORECASE)
    if m:
        n_intermediate = int(m.group(1))

    is_continuous = bool(re.search(r'continuous', ocr, re.IGNORECASE))
    is_distributed = any(u.lower() in ('k/ft', 'kip/ft', 'kn/m') for _, u in loads_found)

    desc  = f"Image: {w}x{h}px, aspect {ratio}.\n\n"
    desc += f"Raw OCR text:\n{raw_ocr}\n\n"
    desc += f"Normalised OCR:\n{ocr}\n\n"

    if is_continuous:
        n_nodes = 2 + n_intermediate  # endpoints + intermediate supports
        n_spans = 1 + n_intermediate
        desc += (
            f"STRUCTURAL INTERPRETATION:\n"
            f"  - Continuous horizontal beam\n"
            f"  - {n_intermediate} intermediate supports -> {n_nodes} nodes, {n_spans} spans, {n_spans} elements\n"
        )

    if spans:
        span_metres = []
        for val, unit in spans:
            v = float(val)
            v_m = round(v * 0.3048, 4) if unit.lower() == 'ft' else v
            span_metres.append(v_m)

        # OCR often drops a leading digit (e.g. "15 ft" -> "5 ft").
        # Heuristic: any span < 40% of average is likely truncated — prepend "1".
        if len(span_metres) > 1:
            avg = sum(span_metres) / len(span_metres)
            corrected = []
            for i, (s_m, (val, unit)) in enumerate(zip(span_metres, spans)):
                if s_m < 0.4 * avg:
                    new_val = float('1' + val)
                    s_m = round(new_val * 0.3048, 4) if unit.lower() == 'ft' else new_val
                corrected.append(s_m)
            span_metres = corrected

        x_coords = [round(sum(span_metres[:i]), 4) for i in range(len(span_metres) + 1)]
        desc += f"  - Span lengths (m): {span_metres}\n"
        desc += f"  - REQUIRED node x-coordinates: {x_coords}\n"
        desc += f"  - You MUST use these exact x values for nodes.\n"

    if is_distributed:
        load_kn = 0.0
        for val, unit in loads_found:
            v = float(val)
            if unit.lower() in ('k/ft', 'kip/ft'):
                load_kn = round(v * 14.5939, 4)
            elif unit.lower() == 'kn/m':
                load_kn = v
        desc += f"  - DISTRIBUTED load = {load_kn} kN/m, applied to EVERY element\n"
    elif loads_found:
        for val, unit in loads_found:
            desc += f"  - Load: {val} {unit}\n"

    if labels:
        desc += f"  - Node labels: {labels}\n"

    desc += "\nIMPORTANT: intermediate supports on a horizontal beam use type='roller_y'.\n"
    return desc


class LemonFoxClient:
    """LemonFox AI client using the OpenAI-compatible API."""

    def __init__(self, api_key: Optional[str] = None):
        key = api_key or os.getenv('LEMONFOX_API_KEY')
        if not key:
            raise ValueError(
                "LemonFox API key not found. "
                "Set the LEMONFOX_API_KEY environment variable."
            )
        self.client = OpenAI(api_key=key, base_url="https://api.lemonfox.ai/v1")
        self.model  = 'llama-70b-chat'

    # ── helpers ───────────────────────────────────────────────────────────────

    def _extract_json(self, text: str) -> str:
        text = text.strip()
        fence = re.search(r'```(?:json)?\s*([\s\S]*?)```', text, re.IGNORECASE)
        if fence:
            text = fence.group(1).strip()
        try:
            json.loads(text)
            return text
        except json.JSONDecodeError:
            pass
        for open_c, close_c in [('{', '}'), ('[', ']')]:
            start = text.find(open_c)
            if start == -1:
                continue
            depth  = 0
            in_str = False
            esc    = False
            for i, ch in enumerate(text[start:], start):
                if esc:                  esc = False;  continue
                if ch == '\\' and in_str: esc = True;  continue
                if ch == '"':            in_str = not in_str; continue
                if in_str:               continue
                if ch == open_c:         depth += 1
                elif ch == close_c:
                    depth -= 1
                    if depth == 0:
                        return text[start:i + 1]
        raise ValueError(f"No JSON found in response.\nRaw (first 400):\n{text[:400]}")

    def _parse_json(self, text: str) -> dict:
        return json.loads(self._extract_json(text))

    def _image_to_base64(self, image_path: str):
        ext  = image_path.rsplit('.', 1)[-1].lower()
        mime = {'jpg': 'image/jpeg', 'jpeg': 'image/jpeg',
                'png': 'image/png',  'gif':  'image/gif',
                'webp': 'image/webp'}.get(ext, 'image/jpeg')
        with open(image_path, 'rb') as f:
            return base64.b64encode(f.read()).decode('utf-8'), mime

    # ── public API ────────────────────────────────────────────────────────────

    def analyze_image(self, image_path: str, prompt: str) -> str:
        """Try vision API first; fall back to OCR + text analysis."""
        b64, mime = self._image_to_base64(image_path)

        # 1. Attempt vision (base64 image_url)
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "image_url",
                         "image_url": {"url": f"data:{mime};base64,{b64}"}},
                        {"type": "text", "text": prompt}
                    ]
                }]
            )
            return response.choices[0].message.content
        except Exception:
            pass

        # 2. OCR + PIL description fallback
        description = _build_text_description(image_path)
        full_prompt = (
            f"A structural engineering drawing was uploaded. "
            f"Here is everything that could be extracted from it:\n\n"
            f"{description}\n\n"
            f"Using this information, build the complete FEM structural model.\n\n"
            f"{prompt}"
        )
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system",
                 "content": "You are a structural engineering assistant. Return only valid JSON."},
                {"role": "user", "content": full_prompt}
            ]
        )
        return response.choices[0].message.content

    def _extract_geometry_from_ocr(self, image_path: str):
        """
        Use OCR to compute definitive node coordinates.
        Returns (x_coords, n_nodes) or (None, None) if not enough info.
        """
        raw_ocr = _ocr_image(image_path)
        if not raw_ocr:
            return None, None

        ocr = raw_ocr
        ocr = re.sub(r'(\d+)\s+[tf]\b', lambda m: m.group(1) + ' ft', ocr)
        ocr = re.sub(r'(\d+)ft\b', r'\1 ft', ocr)
        ocr = re.sub(r'(\d+(?:\.\d+)?)\s*k\b(?!/)', r'\1 k/ft', ocr)

        spans_raw = re.findall(r'(\d+(?:\.\d+)?)\s*(ft|m|mm)\b', ocr, re.IGNORECASE)
        if not spans_raw:
            return None, None

        span_metres = []
        for val, unit in spans_raw:
            v = float(val)
            v_m = round(v * 0.3048, 4) if unit.lower() == 'ft' else v
            span_metres.append(v_m)

        # Correct OCR-truncated spans (< 40% of average)
        if len(span_metres) > 1:
            avg = sum(span_metres) / len(span_metres)
            corrected = []
            for s_m, (val, unit) in zip(span_metres, spans_raw):
                if s_m < 0.4 * avg:
                    new_val = float('1' + val)
                    s_m = round(new_val * 0.3048, 4) if unit.lower() == 'ft' else new_val
                corrected.append(s_m)
            span_metres = corrected

        x_coords = [round(sum(span_metres[:i]), 4) for i in range(len(span_metres) + 1)]
        return x_coords, len(x_coords)

    def extract_structure_from_image(self, image_path: str) -> dict:
        raw = self.analyze_image(image_path, EXTRACTION_PROMPT)
        try:
            result = self._parse_json(raw)
        except (json.JSONDecodeError, ValueError) as e:
            raise ValueError(
                f"LemonFox returned non-JSON output.\n"
                f"Parse error: {e}\n"
                f"Response (first 400): {raw[:400]}"
            )

        # Override node coordinates with OCR-computed geometry (more reliable)
        x_coords, n_ocr = self._extract_geometry_from_ocr(image_path)
        nodes = result.get('nodes', [])
        if x_coords and len(x_coords) == len(nodes):
            for node, x in zip(nodes, x_coords):
                node['x'] = x
                node['y'] = 0.0

        return result

    def repair_structural_data(self, structure_data: dict) -> dict:
        prompt = f"""You are a structural engineer reviewing auto-extracted FEM data.

Check and repair:
1. Element references — all node_i / node_j must exist in nodes list
2. Support coverage — total constrained DOF >= 3 (pin=2, fixed=3, roller=1)
3. Distributed loads must have one entry PER ELEMENT, not one for the whole beam
4. Duplicate node IDs — merge if coordinates within 0.1 units

Input data:
{json.dumps(structure_data, indent=2)}

Return STRICT JSON only — same schema plus a "repairs" array.
No markdown. No explanation."""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system",
                     "content": "You are a structural engineering assistant. Return only valid JSON."},
                    {"role": "user", "content": prompt}
                ]
            )
            result = self._parse_json(response.choices[0].message.content)
            result.setdefault('repairs', [])
            return result
        except Exception:
            structure_data.setdefault('repairs', [])
            return structure_data
