"""
Context Grounder: Compacts raw visual and audio context into a token-efficient
representation designed for Needle 3's 1,024-token local attention horizon.
"""

from typing import Any, Dict, List, Optional


class ContextGrounder:
    """
    Transforms dense Mirage vision outputs (bounding boxes, object lists, OCR tokens)
    into compact spatial anchors (e.g. 'obj_0:terminal_error@top_left') to prevent
    context window blowout.
    """

    def __init__(self, confidence_threshold: float = 0.65, max_objects: int = 6):
        self.confidence_threshold = confidence_threshold
        self.max_objects = max_objects

    def _quadrant_anchor(self, bbox: List[float]) -> str:
        """
        Maps normalized coordinates [ymin, xmin, ymax, xmax] to coarse spatial anchors.
        Saves ~24 tokens per object compared to floating-point coordinate lists.
        """
        if len(bbox) < 4:
            return "center"
        cy = (bbox[0] + bbox[2]) / 2.0
        cx = (bbox[1] + bbox[3]) / 2.0

        v = "top" if cy < 0.35 else ("bottom" if cy > 0.65 else "mid")
        h = "left" if cx < 0.35 else ("right" if cx > 0.65 else "center")
        return f"{v}_{h}"

    def ground_mirage_output(self, mirage_data: Any) -> str:
        """
        Parses either a dict from Mirage or raw text description into a compact string.
        """
        if isinstance(mirage_data, str):
            # If Mirage returned a plain text string summary, truncate to 200 chars
            return f"[SCENE_SUMMARY: {mirage_data[:250].strip()}]"

        if not isinstance(mirage_data, dict):
            return "[SCENE: desktop_active]"

        objects = mirage_data.get("objects", [])
        text_regions = mirage_data.get("text", [])

        # Filter and rank objects by confidence
        valid_objs = [
            obj for obj in objects
            if obj.get("confidence", 0.0) >= self.confidence_threshold
        ]
        valid_objs = sorted(valid_objs, key=lambda x: x.get("confidence", 0.0), reverse=True)[:self.max_objects]

        anchored_entities = []
        for idx, obj in enumerate(valid_objs):
            label = obj.get("name", "window").replace(" ", "_").lower()
            bbox = obj.get("bbox", [0.5, 0.5, 0.5, 0.5])
            anchor = self._quadrant_anchor(bbox)
            anchored_entities.append(f"obj_{idx}:{label}@{anchor}")

        # Top OCR strings (limit to 3 high-confidence strings to save tokens)
        ocr_snippets = []
        for item in text_regions:
            if isinstance(item, dict) and item.get("confidence", 0.0) >= 0.70:
                t = item.get("text", "").replace('"', "'").strip()
                if t:
                    ocr_snippets.append(f'"{t[:40]}"')
            elif isinstance(item, str) and item.strip():
                ocr_snippets.append(f'"{item[:40]}"')

        scene_part = " ".join(anchored_entities) if anchored_entities else "desktop_idle"
        ocr_part = " ".join(ocr_snippets[:3]) if ocr_snippets else "none"

        return f"[SCENE: {scene_part}] [OCR: {ocr_part}]"

    def compose_prompt(self, user_intent: str, grounded_scene: str) -> str:
        """
        Composes prompt placing user intent first so Needle 3 matches intent immediately,
        with optional visual context appended.
        """
        if grounded_scene and "desktop_active" not in grounded_scene:
            return f"{user_intent.strip()} (Context: {grounded_scene})"
        return user_intent.strip()

