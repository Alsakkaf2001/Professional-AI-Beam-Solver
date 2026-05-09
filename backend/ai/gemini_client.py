"""Google Gemini client for structural image analysis (google-genai SDK)."""
import json
import os
import re
from typing import Optional
from google import genai
from google.genai import types
from PIL import Image


EXTRACTION_PROMPT = """You are a structural engineering AI assistant.

Analyze the uploaded beam or frame drawing.

Detect and extract:
- nodes (joints, endpoints, intersections)
- beam members (horizontal, vertical, inclined)
- supports (fixed wall, pin triangle, roller circle)
- point loads (arrows at nodes with magnitude labels)
- distributed loads (UDL — rows of arrows on members)
- dimensions (span lengths, load values)

Return STRICT JSON only. No markdown. No explanation. No comments.

Use this exact schema:

{
  "nodes": [
    {"id": 1, "x": 0.0, "y": 0.0}
  ],
  "elements": [
    {"id": 1, "node_i": 1, "node_j": 2}
  ],
  "supports": [
    {"node_id": 1, "type": "pin"}
  ],
  "loads": [
    {"type": "point",       "node_id": 2, "magnitude_kN": 10.0, "direction": "down"},
    {"type": "distributed", "element_id": 1, "magnitude_kN": 5.0}
  ]
}

Coordinate rules:
- x increases left to right (0 = leftmost node)
- y = 0 for all nodes on a horizontal beam; y increases upward for frames
- Use real dimensions in metres if readable from the image; otherwise normalise so the longest span = 10.0
- Distributed load magnitude: use kN/m (or k/ft converted to kN/m if needed)

Support types: "pin", "fixed", "roller_x", "roller_y"
Load directions: "down", "up", "left", "right"

Only return valid JSON — nothing else."""


class GeminiClient:
    """Gemini vision + text client using the google-genai SDK."""

    def __init__(self, api_key: Optional[str] = None):
        key = api_key or os.getenv('GEMINI_API_KEY')
        if not key:
            raise ValueError(
                "Gemini API key not found. "
                "Set the GEMINI_API_KEY environment variable."
            )
        self.client = genai.Client(api_key=key)
        self.model  = 'gemini-2.0-flash-lite'

    # ── helpers ───────────────────────────────────────────────────────────────

    def _extract_json(self, text: str) -> str:
        """Pull the first complete JSON object or array from any text."""
        text = text.strip()

        # 1. strip markdown fences
        fence = re.search(r'```(?:json)?\s*([\s\S]*?)```', text, re.IGNORECASE)
        if fence:
            text = fence.group(1).strip()

        # 2. direct parse
        try:
            json.loads(text)
            return text
        except json.JSONDecodeError:
            pass

        # 3. scan for outermost { } or [ ]
        for open_c, close_c in [('{', '}'), ('[', ']')]:
            start = text.find(open_c)
            if start == -1:
                continue
            depth  = 0
            in_str = False
            esc    = False
            for i, ch in enumerate(text[start:], start):
                if esc:         esc = False;  continue
                if ch == '\\' and in_str: esc = True; continue
                if ch == '"':   in_str = not in_str; continue
                if in_str:      continue
                if ch == open_c:  depth += 1
                elif ch == close_c:
                    depth -= 1
                    if depth == 0:
                        return text[start:i + 1]

        raise ValueError(
            f"No JSON object found in response.\n"
            f"Raw text (first 400 chars):\n{text[:400]}"
        )

    def _parse_json(self, text: str) -> dict:
        return json.loads(self._extract_json(text))

    # ── public API ────────────────────────────────────────────────────────────

    def analyze_image(self, image: Image.Image, prompt: str) -> str:
        """Send a PIL image + prompt to Gemini and return the raw text."""
        response = self.client.models.generate_content(
            model=self.model,
            contents=[prompt, image]
        )
        return response.text

    def extract_structure_from_image(self, image_path: str) -> dict:
        """
        Analyse a structural drawing image and return FEM model data.
        Returns dict with keys: nodes, elements, supports, loads
        """
        image = Image.open(image_path)
        raw   = self.analyze_image(image, EXTRACTION_PROMPT)
        try:
            return self._parse_json(raw)
        except (json.JSONDecodeError, ValueError) as e:
            raise ValueError(
                f"Gemini returned non-JSON output.\n"
                f"Parse error: {e}\n"
                f"Response (first 400 chars): {raw[:400]}"
            )

    def repair_structural_data(self, structure_data: dict) -> dict:
        """Ask Gemini to validate and repair extracted structural data."""
        prompt = f"""You are a structural engineer reviewing auto-extracted FEM data.

Check and repair:
1. Element references — all node_i / node_j must exist in nodes list
2. Support coverage — total constrained DOF >= 3 (pin=2, fixed=3, roller=1)
3. Duplicate node IDs — merge if coordinates within 0.1 units
4. Disconnected nodes — warn if unreachable

Input data:
{json.dumps(structure_data, indent=2)}

Return STRICT JSON only — same schema plus a "repairs" array.
No markdown. No explanation."""

        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt
            )
            result = self._parse_json(response.text)
            result.setdefault('repairs', [])
            return result
        except Exception:
            structure_data.setdefault('repairs', [])
            return structure_data
