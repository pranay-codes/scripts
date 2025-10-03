#!/usr/bin/env python3
"""
pdf_vector_raster_inspector.py

Purpose:
  Detect, per page of a PDF, whether the page contains raster (image) content
  and/or vector content (drawings and/or selectable text). Output a JSON report
  that matches the requested schema per page.

Output schema per page (as a list of such dicts):
{
  "page": 1,
  "vector_content": true,
  "raster_content": true,
  "raster_objects": ["logo", "stamp"],
  "vector_objects": ["lines", "text", "paths"]
}

Notes:
  - Uses PyMuPDF (fitz) for PDF parsing.
  - Heuristics are used to label raster objects as 'logo', 'stamp',
    'scanned_page', or 'image' based on size and placement.
  - 'vector_objects' includes 'text' if the page has selectable text, 'lines'
    if simple line/rect/polyline drawings exist, and 'paths' when curves /
    bezier / complex shapes appear.

Install:
  pip install pymupdf

Usage:
  python pdf_vector_raster_inspector.py input.pdf > report.json
"""

import argparse
import json
import sys
from typing import List, Dict, Any, Set

try:
    import fitz  # PyMuPDF
except Exception as e:
    print("Error: PyMuPDF is required. Install with 'pip install pymupdf'.", file=sys.stderr)
    raise


def classify_raster_block(bbox, page_w, page_h) -> str:
    """
    Heuristically classify an image block based on its size and location.

    Returns one of: 'scanned_page', 'large_image', 'logo', 'stamp', 'image'
    """
    x0, y0, x1, y1 = bbox
    bw = max(0.0, x1 - x0)
    bh = max(0.0, y1 - y0)
    area = bw * bh
    page_area = max(1.0, page_w * page_h)
    ratio = area / page_area

    # Corners / edges helpers
    near_top = y0 <= 0.15 * page_h
    near_bottom = y1 >= 0.85 * page_h
    near_right = x1 >= 0.85 * page_w
    near_left = x0 <= 0.15 * page_w

    # Heuristics
    if ratio >= 0.6:
        return "scanned_page"
    if ratio >= 0.1:
        return "large_image"

    # Small images: distinguish logo vs stamp by placement
    if ratio <= 0.02:
        # Common: logo at top-left/top-right, stamp at bottom-right/bottom
        if near_bottom and (near_right or near_left):
            return "stamp"
        if near_top and (near_right or near_left):
            return "logo"
        # Fallback
        return "image"

    # Medium-small generic
    return "image"


def get_image_blocks(page) -> List[Dict[str, Any]]:
    """
    Return image blocks with bounding boxes via page.get_text('dict').
    Each block: {"type": 1, "bbox": [x0, y0, x1, y1], ...}
    """
    blocks = []
    text_dict = page.get_text("dict")
    for b in text_dict.get("blocks", []):
        if b.get("type") == 1 and "bbox" in b:
            blocks.append(b)
    return blocks


def collect_vector_kinds_from_drawings(drawings: List[Dict[str, Any]]) -> Set[str]:
    """
    Inspect drawing items returned by page.get_drawings() and infer whether
    we saw simple 'lines' and/or more complex 'paths'.
    """

    OPERATOR_MAP = {
        "l": "line",
        "c": "curve",
        "re": "rect",
        "m": "moveto",
        "h": "closepath",
        "q": "save_state",
        "Q": "restore_state",
        "qu": "quad"
    }
    
    kinds = set()
    for d in drawings:
        for item in d.get("items", []):
            # Ensure item is a dictionary before accessing its properties
            print("item:", item)
            if isinstance(item, dict):
                t = item.get("type", "").lower()
                kinds.add(t)
            elif isinstance(item, tuple):
                # Handle tuple case (log or process as needed)
                op = str(item[0]).lower()
                obj_type = OPERATOR_MAP.get(op, op)  # default to op if not mapped
                kinds.add(obj_type)
    return kinds


def analyze_pdf(pdf_path: str) -> List[Dict[str, Any]]:
    doc = fitz.open(pdf_path)
    results: List[Dict[str, Any]] = []

    for i, page in enumerate(doc, start=1):
        page_rect = page.rect
        page_w, page_h = page_rect.width, page_rect.height

        # Raster detection via image blocks (with positions)
        image_blocks = get_image_blocks(page)
        raster_labels: Set[str] = set()
        for ib in image_blocks:
            label = classify_raster_block(ib["bbox"], page_w, page_h)
            raster_labels.add(label)

        # Vector detection:
        #   - selectable text
        #   - vectors via get_drawings()
        has_text = len(page.get_text("words")) > 0
        drawings = page.get_drawings()
        vector_kinds = collect_vector_kinds_from_drawings(drawings)

        vector_objects = []
        if has_text:
            vector_objects.append("text")
        vector_objects.extend(sorted(vector_kinds))

        page_result = {
            "page": i,
            "vector_content": bool(vector_objects),
            "raster_content": bool(image_blocks),
            "raster_objects": sorted(raster_labels) if raster_labels else [],
            "vector_objects": vector_objects if vector_objects else []
        }
        results.append(page_result)

    doc.close()
    return results


def main():
    parser = argparse.ArgumentParser(description="Detect raster vs vector content in a PDF (per page).")
    parser.add_argument("pdf", help="Path to the PDF file to analyze.")
    parser.add_argument("-o", "--output", help="Path to write JSON output (defaults to stdout).")
    args = parser.parse_args()

    report = analyze_pdf(args.pdf)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
    else:
        json.dump(report, sys.stdout, indent=2)


if __name__ == "__main__":
    main()
