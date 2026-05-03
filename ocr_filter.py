#!/usr/bin/env python3
"""
OCR Result Filter for FSE Frame Analysis

Filters raw OCR results to keep only medically relevant fields needed
for prescription generation and database storage.

Kept fields:
  - Patient name, NIR/IPP
  - Prescriber (P.Code, name, RPPS)
  - Practitioner name
  - AMY procedure codes
  - Dates (prescription, act)
  - FSE/dossier number
  - Establishment name
  - Montant (amount)

Discarded:
  - OS/app UI noise (TeamViewer, IP addresses, taskbar, OpenOffice, etc.)
  - Single-character misdetections
  - CJK false positives
  - Generic button labels (Imprimer, Sauvegarde, Fermer, etc.)
"""

import re
from typing import Dict, List, Optional


# ── Patterns to DISCARD (noise from desktop/app UI) ──────────────────────────

_NOISE_EXACT = {
    # Remote desktop / OS
    "TeamViewer", "bat Reader", "Tat Reader", "OpenOffice 4.1.6",
    "Orthofast", "Orthofast Glient", "Orthofast Client",
    # Galaxie UI buttons (not useful for extraction)
    "Imprimer", "Sauvegarde", "Reinitialisation", "Fermer Session",
    "Nouveau dossier", "dossier inutile", "Chgt Msg", "Courriers",
    "Texte libre", "Effacer", "Corbeille", "Encours", "En cours",
    "Gestionnaire de", "rapprochement", "dentaire",
    "Centre2Soins", "la carte CPs",
    # Galaxie UI labels / column headers
    "Date acte", "Date acte:", "Nb Libellé acte", "Parcours", "Risque",
    "Taux", "Base Remb", "Commun", "Gestion desActes", "Gestion des Actes",
    "TiersPayant", "Tiers Payant", "Nom praticien", "Nom pralicien",
    "Dossier N'FSE", "DossierN'FSE",
    "Autre Patient", "Ophtalmologue",
    # Galaxie form field labels
    "Etablissement:", "Actes", "Actes:", "Montant", "Acte:",
    "Quanté:", "Quantité:", "Code EP:", "CodeEP:", "Date EP:",
    "Couv.Soc.:", "Couv. Soc.:", "Parcours de soins:",
    "Dt prescription", "Dt prescription:",
    "Praticien", "Praticien:",
    "Acte non soumis a accord préalable",
    "Acte non soumis à accord préalable",
    # OCR-mangled Galaxie button labels
    "Ajouger", "Ajouter", "Enregatre", "Enregistrer",
    "Eacturer", "Facturer", "Acte defot", "Acte défaut",
    "guter", "Quter", "crD",
    # Misc noise
    "CDR", "ref", "REF", "REFVC", "PYX", "PVX",
    "la carte CPS", "la carte CPs", "AS",
}

_NOISE_PATTERNS = [
    re.compile(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$'),  # IP addresses
    re.compile(r'^[\u4e00-\u9fff\u2e80-\u2fd5]+$'),          # CJK-only (misdetections)
    re.compile(r'^[□√✓✗×]+$'),                                # Checkboxes/symbols
    re.compile(r'^[+\-=|_]{1,3}$'),                           # Decorative characters
    re.compile(r'^\d{2}:\d{2}$'),                             # Clock time (07:37)
    re.compile(r'^F\d$'),                                      # Function key refs (F9)
    re.compile(r'la touche F\d'),                              # "la touche F9 vous permet..."
    re.compile(r'^GALAXIE\b'),                                  # Software version strings
    re.compile(r'^atReader$'),                                   # OCR mangled "bat Reader"
    re.compile(r'^[∆A]utre\s*Patient', re.IGNORECASE),          # Mangled "Autre Patient"
    re.compile(r'^REF\('),                                       # REF(20.80€) reference labels
    re.compile(r'^\d+%\d'),                                     # "50%20.806" percentage noise
    re.compile(r'^\d+%$'),                                       # "150%" standalone percentage
    re.compile(r'^Maladie \d'),                                   # "Maladie 01751 du ..." coverage line
]

# Minimum confidence to keep any result
MIN_CONFIDENCE = 0.35

# Single characters are almost always noise (except specific ones)
_SINGLE_CHAR_KEEP = set()  # None worth keeping


# ── Patterns to IDENTIFY as relevant fields ───────────────────────────────────

def _is_patient_name(text: str) -> bool:
    t = text.upper().strip()
    # Known test patient or pattern "LASTNAME FIRSTNAME"
    return bool(re.match(r'^[A-ZÉÈÊËÀÂÄÙÛÜÔÖÎÏÇ\- ]{3,}$', t) and len(t.split()) <= 4)


def _is_amy_code(text: str) -> bool:
    return bool(re.search(r'AMY\s*\d', text, re.IGNORECASE))


def _is_date(text: str) -> bool:
    return bool(re.search(r'\d{2}/\d{2}/\d{4}', text))


def _is_rpps(text: str) -> bool:
    # RPPS is exactly 11 digits, standalone (not embedded in longer text with letters)
    clean = text.strip()
    digits = re.sub(r'\D', '', clean)
    # Must be primarily numeric (at most "RPPS:" prefix)
    return len(digits) == 11 and bool(re.match(r'^(RPPS\s*:?\s*)?\d[\d\s]{9,}\d$', clean, re.IGNORECASE))


def _is_nir(text: str) -> bool:
    clean = re.sub(r'\D', '', text)
    return 13 <= len(clean) <= 15


def _is_fse_number(text: str) -> bool:
    """FSE/dossier numbers: typically 5-6+ digit sequences"""
    return bool(re.match(r'^\d{5,}', text.strip()))


def _is_prescriber_line(text: str) -> bool:
    t = text.lower()
    # Handle OCR typos: "Prescripteur", "Prescipteur", "Prescribteur", etc.
    return bool(re.search(r'presc[ri]*[pb]?teur', t))


def _is_practitioner_line(text: str) -> bool:
    t = text.lower()
    # "ACHATOUHMAROUAN(Orthoptiste)" or "ACHATOUH MAROUAN (Orhoptiste)"
    return 'orthoptiste' in t or 'orhoptiste' in t


def _is_establishment(text: str) -> bool:
    t = text.upper()
    return 'CDS ' in t or 'OPHTALMOLOGIE' in t or 'CENTRE DE SOINS' in t


def _is_montant(text: str) -> bool:
    return bool(re.search(r'\d+[,\.]\d{2}\s*€?$', text))


def _is_ipp_line(text: str) -> bool:
    """IPP pattern: digits with > separator e.g. '15035-2770399312069'"""
    return bool(re.match(r'^\d{4,}-\d+', text.strip()))


# ── Main filter ───────────────────────────────────────────────────────────────

def is_noise(text: str, confidence: float) -> bool:
    """Return True if this OCR result should be discarded."""
    stripped = text.strip()

    # Empty
    if not stripped:
        return True

    # Below confidence threshold
    if confidence < MIN_CONFIDENCE:
        return True

    # Single character (almost always noise)
    if len(stripped) <= 1 and stripped not in _SINGLE_CHAR_KEEP:
        return True

    # Two characters that aren't a known code
    if len(stripped) == 2 and stripped.isalpha() and not stripped.isupper():
        return True

    # Exact match noise
    if stripped in _NOISE_EXACT:
        return True

    # Pattern-based noise
    for pattern in _NOISE_PATTERNS:
        if pattern.search(stripped):
            return True

    return False


def classify_field(text: str) -> Optional[str]:
    """Classify a relevant OCR text into a field category. Returns None if generic."""
    if _is_amy_code(text):
        return "amy_code"
    if _is_prescriber_line(text):
        return "prescriber"
    if _is_practitioner_line(text):
        return "practitioner"
    if _is_establishment(text):
        return "establishment"
    if _is_ipp_line(text):
        return "ipp"
    if _is_rpps(text):
        return "rpps"
    if _is_nir(text):
        return "nir"
    if _is_montant(text):
        return "montant"
    if _is_date(text):
        return "date"
    if _is_fse_number(text):
        return "fse_number"
    return None


def filter_frame_ocr(ocr_results: List[Dict]) -> Dict:
    """
    Filter a single frame's OCR results, keeping only medically relevant data.

    Args:
        ocr_results: List of {"text": str, "confidence": float}

    Returns:
        {
            "relevant_texts": [{"text": ..., "confidence": ..., "field": ...}, ...],
            "detected_fields": {
                "patient_name": str | None,
                "prescriber": str | None,
                "practitioner": str | None,
                "establishment": str | None,
                "rpps": str | None,
                "nir": str | None,
                "ipp": str | None,
                "amy_codes": [str],
                "dates": [str],
                "fse_number": str | None,
                "montant": str | None,
            }
        }
    """
    relevant = []
    fields = {
        "patient_name": None,
        "prescriber": None,
        "practitioner": None,
        "establishment": None,
        "rpps": None,
        "nir": None,
        "ipp": None,
        "amy_codes": [],
        "dates": [],
        "fse_number": None,
        "montant": None,
    }

    for item in ocr_results:
        text = item.get("text", "")
        conf = item.get("confidence", 0)

        if is_noise(text, conf):
            continue

        field_type = classify_field(text)
        entry = {"text": text, "confidence": conf}
        if field_type:
            entry["field"] = field_type

        relevant.append(entry)

        # Populate detected_fields
        if field_type == "amy_code":
            fields["amy_codes"].append(text)
        elif field_type == "prescriber":
            # Extract name from "Prescripteur:BAZ" combined text
            colon_match = re.search(r'[:\s]+([A-ZÉÈÊËÀÂÄÙÛÜÔÖÎÏÇ\-, ]{2,})$', text.strip())
            if colon_match:
                fields["prescriber"] = colon_match.group(1).strip()
            else:
                fields["prescriber"] = text
        elif field_type == "practitioner":
            fields["practitioner"] = text
        elif field_type == "establishment":
            fields["establishment"] = text
        elif field_type == "rpps":
            fields["rpps"] = text
        elif field_type == "nir":
            fields["nir"] = text
        elif field_type == "ipp":
            fields["ipp"] = text
        elif field_type == "date":
            fields["dates"].append(text)
        elif field_type == "fse_number":
            if fields["fse_number"] is None:
                fields["fse_number"] = text
        elif field_type == "montant":
            fields["montant"] = text
        elif field_type is None:
            # Unclassified but not noise — check if it's a patient name candidate
            upper = text.upper().strip()
            if _is_patient_name(text) and "patient_name" not in [e.get("field") for e in relevant]:
                # Heuristic: known test patient
                if "TEST" in upper and "IDEM" in upper:
                    fields["patient_name"] = text
                    entry["field"] = "patient_name"

    # ── Second pass: context-aware prescriber name enrichment ──────────────
    # If prescriber was extracted as a short name (e.g., "BAZ" from "Prescipteur:BAZ"),
    # look for a fuller name nearby (e.g., "BAZ, PATRICK").
    _NAME_RE = re.compile(r'^[A-ZÉÈÊËÀÂÄÙÛÜÔÖÎÏÇ\-, ]{3,}$')

    if fields["prescriber"]:
        prescriber_idx = next(
            (i for i, e in enumerate(relevant) if e.get("field") == "prescriber"), None
        )
        if prescriber_idx is not None:
            # Look in the next few entries for a fuller name
            for j in range(prescriber_idx + 1, min(prescriber_idx + 4, len(relevant))):
                candidate = relevant[j]
                if candidate.get("field"):
                    continue  # already tagged
                ct = candidate["text"].strip()
                # "BAZ, PATRICK" — uppercase name with comma, longer than current
                if _NAME_RE.match(ct) and ',' in ct and len(ct) > len(fields["prescriber"]):
                    fields["prescriber"] = ct
                    candidate["field"] = "prescriber"
                    break

    return {
        "relevant_texts": relevant,
        "detected_fields": fields,
    }


def filter_analysis_data(analysis_data: Dict) -> Dict:
    """
    Filter an entire analysis_data.json, replacing raw ocr_results + detected_fields
    with filtered versions.

    Args:
        analysis_data: Full JSON structure from analyze_video.py

    Returns:
        Same structure but with filtered ocr results
    """
    filtered = {
        "video_path": analysis_data.get("video_path"),
        "analysis_date": analysis_data.get("analysis_date"),
        "total_frames_extracted": analysis_data.get("total_frames_extracted"),
        "frames": [],
    }

    for frame in analysis_data.get("frames", []):
        raw_ocr = frame.get("ocr_results", [])
        result = filter_frame_ocr(raw_ocr)

        filtered["frames"].append({
            "frame_number": frame.get("frame_number"),
            "timestamp_seconds": frame.get("timestamp_seconds"),
            "filename": frame.get("filename"),
            "relevant_texts": result["relevant_texts"],
            "detected_fields": result["detected_fields"],
        })

    return filtered


# ── CLI: filter existing analysis_data.json ──────────────────────────────────

if __name__ == "__main__":
    import json
    import sys
    from pathlib import Path

    input_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent / "video_analysis" / "analysis_data.json"
    output_path = input_path.parent / "analysis_data_filtered.json"

    print(f"Reading: {input_path}")
    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    filtered = filter_analysis_data(data)

    # Stats
    total_raw = sum(len(fr.get("ocr_results", [])) for fr in data.get("frames", []))
    total_kept = sum(len(fr.get("relevant_texts", [])) for fr in filtered.get("frames", []))
    print(f"Raw OCR entries: {total_raw}")
    print(f"Kept (relevant): {total_kept}")
    print(f"Discarded:       {total_raw - total_kept} ({100*(total_raw-total_kept)/max(total_raw,1):.0f}%)")

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(filtered, f, indent=2, ensure_ascii=False)

    print(f"Saved: {output_path}")
