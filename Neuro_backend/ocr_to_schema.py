#!/usr/bin/env python3
"""
OCR Filter → Extraction Schema adapter
Converts ocr_filter.py output to openai_extraction.py schema
WITHOUT needing any API key
"""
import re
from typing import Dict, Optional, List
from datetime import datetime


def normalize_amy_code(raw: str) -> Optional[str]:
    match = re.search(r'AMY\s*\(?\s*(\d+(?:[,\.]\d+)?)\s*\)?', raw, re.IGNORECASE)
    if not match:
        return None
    num = match.group(1).replace('.', ',')
    return f'AMY {num}'


def convert_date_fr_to_iso(date_str: Optional[str]) -> Optional[str]:
    """Convert DD/MM/YYYY to YYYY-MM-DD"""
    if not date_str:
        return None
    match = re.search(r'(\d{2})/(\d{2})/(\d{4})', date_str)
    if match:
        return f"{match.group(3)}-{match.group(2)}-{match.group(1)}"
    return None


def ocr_fields_to_schema(detected_fields: Dict, ocr_raw_text: str = "") -> Dict:
    # --- Patient name ---
    last_name = None
    first_name = None
    raw_name = detected_fields.get("patient_name")
    if raw_name:
        parts = raw_name.strip().split()
        if len(parts) >= 2:
            last_name = parts[0]
            first_name = " ".join(parts[1:])
        else:
            last_name = raw_name

    # --- NIR ---
    nir = detected_fields.get("nir")

    # --- Dates ---
    dates = detected_fields.get("dates", [])
    form_date = None

    if dates:
        # First date = form date (act date)
        form_date = convert_date_fr_to_iso(dates[0]) if len(dates) > 0 else None

    # birth_date is NOT extracted from FSE screen — it shows act date, not birth date
    birth_date = None

    # --- Doctor ---
    prescriber = detected_fields.get("prescriber")
    rpps_raw = detected_fields.get("rpps")
    rpps = rpps_raw if rpps_raw else None  # keep as-is (may have letters like 7594977I)

    # --- AMY codes ---
    amy_codes_raw = detected_fields.get("amy_codes", [])
    acts_prescribed = []
    for code in amy_codes_raw:
        normalized = normalize_amy_code(code)
        if normalized and normalized not in acts_prescribed:
            acts_prescribed.append(normalized)

    return {
        "form_date": form_date,
        "patient": {
            "last_name": last_name,
            "first_name": first_name,
            "nir": nir,
            "birth_date": birth_date,
        },
        "doctor": {
            "full_name": prescriber,
            "rpps": rpps,
        },
        "orthoptic_care": {
            "description": None,
            "acts_prescribed": acts_prescribed,
        },
        "ocr_raw_text": ocr_raw_text,
    }


def extract_from_ocr_results(ocr_results: List[Dict]) -> Dict:
    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from ocr_filter import filter_frame_ocr

    filtered = filter_frame_ocr(ocr_results)
    detected = filtered["detected_fields"]
    raw_text = "\n".join(
        item["text"] for item in filtered["relevant_texts"]
    )

    return ocr_fields_to_schema(detected, raw_text)


if __name__ == "__main__":
    import json

    test_ocr = [
        {"text": "WESOLOWSKA-EISL NINA", "confidence": 0.95},
        {"text": "28/10/2025", "confidence": 0.92},
        {"text": "Opérateur : CHAVANNES, SYLVIEla touche F9 vous permet de dupliquer un acte.", "confidence": 0.99},
        {"text": "AMY 8", "confidence": 0.94},
        {"text": "C9 Maladie 01751 du 01/01/2024 au 30/09/2025 TP -TP RC: 7594977I", "confidence": 0.85},
    ]

    result = extract_from_ocr_results(test_ocr)
    print(json.dumps(result, indent=2, ensure_ascii=False))