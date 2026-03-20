#!/usr/bin/env python3
"""
OCR Filter → Extraction Schema adapter
Converts ocr_filter.py output to prescription schema.
Enriches prescriber with RPPS from practitioners DB.
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


def _lookup_practitioner(prescriber_name: str, pcode: Optional[str] = None) -> Optional[Dict]:
    """
    Look up practitioner in DB by P.Code or name.
    Returns dict with full_name, rpps or None.
    """
    try:
        import sys, os
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from practitioners import get_practitioner_by_pcode, get_practitioner_by_name

        # Try by P.Code first (most reliable)
        if pcode:
            result = get_practitioner_by_pcode(pcode)
            if result:
                return result

        # Try by name (fuzzy match)
        if prescriber_name:
            result = get_practitioner_by_name(prescriber_name)
            if result:
                return result

    except Exception as e:
        pass  # DB not available — use OCR data as-is

    return None


def ocr_fields_to_schema(detected_fields: Dict, ocr_raw_text: str = "") -> Dict:
    """
    Convert detected_fields from ocr_filter.py to prescription schema.
    Enriches prescriber with RPPS from practitioners DB.
    """

    # --- Patient name ---
    last_name = None
    first_name = None
    raw_name = detected_fields.get("patient_name")
    if raw_name:
        parts = raw_name.strip().split()
        if len(parts) >= 2:
            last_name  = parts[0]
            first_name = " ".join(parts[1:])
        else:
            last_name = raw_name

    # --- NIR ---
    nir = detected_fields.get("nir")

    # --- Dates ---
    dates = detected_fields.get("dates", [])
    form_date  = convert_date_fr_to_iso(dates[0]) if len(dates) > 0 else None
    birth_date = None  # FSE screen does not show birth date reliably

    # --- Prescriber + RPPS ---
    prescriber_raw = detected_fields.get("prescriber") or ""
    rpps_raw       = detected_fields.get("rpps")

    # Try to enrich from DB
    practitioner = _lookup_practitioner(prescriber_raw)

    if practitioner:
        # DB match found — use canonical name and RPPS
        full_name = practitioner["full_name"]
        rpps      = practitioner["rpps"] or rpps_raw
    else:
        # No DB match — use OCR data
        full_name = prescriber_raw
        rpps      = rpps_raw

    # --- AMY codes ---
    amy_codes_raw  = detected_fields.get("amy_codes", [])
    acts_prescribed = []
    for code in amy_codes_raw:
        normalized = normalize_amy_code(code)
        if normalized and normalized not in acts_prescribed:
            acts_prescribed.append(normalized)

    # --- IPP ---
    ipp = detected_fields.get("ipp")

    # --- FSE number ---
    fse_number = detected_fields.get("fse_number")

    return {
        "form_date": form_date,
        "fse_number": fse_number,
        "patient": {
            "last_name":  last_name,
            "first_name": first_name,
            "nir":        nir,
            "birth_date": birth_date,
            "ipp":        ipp,
        },
        "doctor": {
            "full_name": full_name,
            "rpps":      rpps,
        },
        "orthoptic_care": {
            "description":    None,
            "acts_prescribed": acts_prescribed,
        },
        "ocr_raw_text": ocr_raw_text,
    }


def extract_from_ocr_results(ocr_results: List[Dict]) -> Dict:
    """
    Full pipeline: ocr_results → ocr_filter → DB lookup → schema
    """
    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from ocr_filter import filter_frame_ocr

    filtered = filter_frame_ocr(ocr_results)
    detected = filtered["detected_fields"]
    raw_text = "\n".join(item["text"] for item in filtered["relevant_texts"])

    return ocr_fields_to_schema(detected, raw_text)


if __name__ == "__main__":
    import json

    test_ocr = [
        {"text": "WESOLOWSKA-EISL NINA", "confidence": 0.95},
        {"text": "28/10/2025",           "confidence": 0.99},
        {"text": "Prescripteur :VS",      "confidence": 0.97},
        {"text": "STANANAMARIA-VERON",    "confidence": 0.99},
        {"text": "AMY 8",                 "confidence": 0.98},
        {"text": "78950 -2 06 12 99 622 925", "confidence": 0.94},
        {"text": "95990",                 "confidence": 0.99},
    ]

    result = extract_from_ocr_results(test_ocr)
    print(json.dumps(result, indent=2, ensure_ascii=False))
