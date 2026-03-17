#!/usr/bin/env python3
"""
OCR Result Filter for FSE Frame Analysis - FIXED
"""

import re
from typing import Dict, List, Optional


# ── Patterns to DISCARD ──────────────────────────────────────────────────────

_NOISE_EXACT = {
    "TeamViewer", "bat Reader", "Tat Reader", "OpenOffice 4.1.6",
    "Orthofast", "Orthofast Glient", "Orthofast Client",
    "Imprimer", "Sauvegarde", "Reinitialisation", "Fermer Session",
    "Nouveau dossier", "dossier inutile", "Chgt Msg", "Courriers",
    "Texte libre", "Effacer", "Corbeille", "Encours", "En cours",
    "Gestionnaire de", "rapprochement", "dentaire",
    "Centre2Soins", "la carte CPs",
    "Date acte", "Date acte:", "Nb Libellé acte", "Parcours", "Risque",
    "Taux", "Base Remb", "Commun", "Gestion desActes", "Gestion des Actes",
    "TiersPayant", "Tiers Payant", "Nom praticien", "Nom pralicien",
    "Dossier N'FSE", "DossierN'FSE",
    "Autre Patient", "Ophtalmologue",
    "Etablissement:", "Actes", "Actes:", "Montant", "Acte:",
    "Quantité:", "Quantité:", "Code EP:", "CodeEP:", "Date EP:",
    "Couv.Soc.:", "Couv. Soc.:", "Parcours de soins:",
    "Dt prescription", "Dt prescription:",
    "Praticien", "Praticien:",
    "Ajouger", "Ajouter", "Enregatre", "Enregistrer",
    "Eacturer", "Facturer", "Acte defot", "Acte défaut",
    "guter", "Quter", "crD", "CDR", "ref", "REF", "REFVC", "PYX", "PVX",
    "la carte CPS", "la carte CPs", "AS",
}

_NOISE_PATTERNS = [
    re.compile(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$'),
    re.compile(r'^[\u4e00-\u9fff\u2e80-\u2fd5]+$'),
    re.compile(r'^[+\-=|_]{1,3}$'),
    re.compile(r'^\d{2}:\d{2}$'),
    re.compile(r'^F\d$'),
    re.compile(r'la touche F\d'),
    re.compile(r'^GALAXIE\b'),
    re.compile(r'^atReader$'),
    re.compile(r'^REF\('),
    re.compile(r'^\d+%\d'),
    re.compile(r'^\d+%$'),
]

MIN_CONFIDENCE = 0.35


# ── Field detection helpers ───────────────────────────────────────────────────

def _is_patient_name(text: str) -> bool:
    t = text.upper().strip()
    return bool(re.match(r'^[A-ZÉÈÊËÀÂÄÙÛÜÓÖÎÏÇ\- ]{3,}$', t) and len(t.split()) <= 4)


def _is_amy_code(text: str) -> bool:
    return bool(re.search(r'AMY\s*\d', text, re.IGNORECASE))


def _is_date(text: str) -> bool:
    return bool(re.search(r'\d{2}/\d{2}/\d{4}', text))


def _is_rpps(text: str) -> bool:
    clean = text.strip()
    digits = re.sub(r'\D', '', clean)
    return len(digits) == 11 and bool(re.match(r'^(RPPS\s*:?\s*)?\d[\d\s]{9,}\d$', clean, re.IGNORECASE))


def _extract_rpps_from_line(text: str) -> Optional[str]:
    match = re.search(r'RC:\s*([A-Z0-9]{7,})', text, re.IGNORECASE)
    if match:
        return match.group(1)
    match = re.search(r'RPPS\s*:?\s*(\d{11})', text, re.IGNORECASE)
    if match:
        return match.group(1)
    return None


def _is_nir(text: str) -> bool:
    clean = re.sub(r'[\s\-]', '', text)
    return bool(re.match(r'^[12]\d{12,14}$', clean))


def _is_fse_number(text: str) -> bool:
    return bool(re.match(r'^\d{5,}', text.strip()))


def _is_prescriber_line(text: str) -> bool:
    t = text.lower()
    return bool(re.search(r'presc[ri]*[pb]?teur|op[eé]rateur', t))


def _is_practitioner_line(text: str) -> bool:
    t = text.lower()
    return 'orthoptiste' in t or 'orhoptiste' in t


def _is_establishment(text: str) -> bool:
    t = text.upper()
    return 'CDS ' in t or 'OPHTALMOLOGIE' in t or 'CENTRE DE SOINS' in t


def _is_montant(text: str) -> bool:
    return bool(re.search(r'\d+[,\.]\d{2}\s*€?$', text))


def _extract_prescriber_name(text: str) -> str:
    """
    Extract doctor name from lines like:
    - 'Operateur : CHAVANNES, SYLVIE'
    - 'Opérateur : CHAVANNES, SYLVIEla touche F9 vous permet...'
    Strategy: find text after colon, keep UPPERCASE chars until first lowercase
    """
    m = re.search(r'(?:op[eé]rateur|prescripteur)\s*:?\s*', text, re.IGNORECASE)
    if not m:
        return text.strip()

    after = text[m.end():].strip()

    # Keep uppercase letters, spaces, commas, hyphens — stop at first lowercase
    name_chars = []
    for ch in after:
        if ch.isupper() or ch in ' ,-':
            name_chars.append(ch)
        elif ch == '\n':
            break
        else:
            break  # lowercase = start of garbage like "la touche..."

    name = ''.join(name_chars).strip(' ,')
    # Remove trailing single letter artifact (e.g. 'I' from 'Ia touche')
    import re as _re
    name = _re.sub(r'\s+[A-Z]$', '', name).strip(' ,')
    return name if name else after.split('la ')[0].strip()


# ── Noise check ───────────────────────────────────────────────────────────────

def is_noise(text: str, confidence: float) -> bool:
    stripped = text.strip()
    if not stripped:
        return True
    if confidence < MIN_CONFIDENCE:
        return True
    if len(stripped) <= 1:
        return True
    if len(stripped) == 2 and stripped.isalpha() and not stripped.isupper():
        return True
    if stripped in _NOISE_EXACT:
        return True
    for pattern in _NOISE_PATTERNS:
        if pattern.search(stripped):
            return True
    return False


def classify_field(text: str) -> Optional[str]:
    if _is_amy_code(text):
        return "amy_code"
    if _is_prescriber_line(text):
        return "prescriber"
    if _is_practitioner_line(text):
        return "practitioner"
    if _is_establishment(text):
        return "establishment"
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


# ── Main filter ───────────────────────────────────────────────────────────────

def filter_frame_ocr(ocr_results: List[Dict]) -> Dict:
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

        # ── PRE-FILTER: extract key fields BEFORE noise check ─────────────
        # Needed because "Opérateur : CHAVANNES, SYLVIEla touche F9..."
        # is classified as noise (contains "la touche F9") but has doctor name

        if _is_prescriber_line(text) and fields["prescriber"] is None:
            fields["prescriber"] = _extract_prescriber_name(text)

        rpps_extracted = _extract_rpps_from_line(text)
        if rpps_extracted and fields["rpps"] is None:
            fields["rpps"] = rpps_extracted

        if _is_date(text):
            date_matches = re.findall(r'\d{2}/\d{2}/\d{4}', text)
            for d in date_matches:
                if d not in fields["dates"]:
                    fields["dates"].append(d)

        # ── Now apply noise filter ────────────────────────────────────────
        if is_noise(text, conf):
            continue

        field_type = classify_field(text)
        entry = {"text": text, "confidence": conf}
        if field_type:
            entry["field"] = field_type

        relevant.append(entry)

        # ── Populate detected_fields ──────────────────────────────────────
        if field_type == "amy_code":
            fields["amy_codes"].append(text)

        elif field_type == "prescriber":
            name = _extract_prescriber_name(text)
            if name:
                fields["prescriber"] = name

        elif field_type == "practitioner":
            fields["practitioner"] = text

        elif field_type == "establishment":
            clean = re.sub(r'^[Ee]tablissement\s*:?\s*', '', text).strip()
            fields["establishment"] = clean

        elif field_type == "rpps":
            if fields["rpps"] is None:
                fields["rpps"] = re.sub(r'\D', '', text)

        elif field_type == "nir":
            if fields["nir"] is None:
                fields["nir"] = text

        elif field_type == "date":
            date_matches = re.findall(r'\d{2}/\d{2}/\d{4}', text)
            for d in date_matches:
                if d not in fields["dates"]:
                    fields["dates"].append(d)

        elif field_type == "fse_number":
            if fields["fse_number"] is None:
                fields["fse_number"] = text

        elif field_type == "montant":
            fields["montant"] = text

        elif field_type is None:
            if fields["patient_name"] is None and _is_patient_name(text):
                fields["patient_name"] = text
                entry["field"] = "patient_name"

    return {
        "relevant_texts": relevant,
        "detected_fields": fields,
    }


def filter_analysis_data(analysis_data: Dict) -> Dict:
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


if __name__ == "__main__":
    import json, sys
    from pathlib import Path

    input_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent / "video_analysis" / "analysis_data.json"
    output_path = input_path.parent / "analysis_data_filtered.json"

    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    filtered = filter_analysis_data(data)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(filtered, f, indent=2, ensure_ascii=False)
    print(f"Saved: {output_path}")