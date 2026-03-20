#!/usr/bin/env python3
"""
OCR Result Filter for FSE Frame Analysis - FIXED
Key fixes:
- NIR-like lines "78950 -2 06 12 99 ..." not classified as fse_number
- "Prescripteur :VS" → look at next line for full name
- Prescriber from merged amount line "8,32@STAN ANAMARIA"
- Opérateur = fallback only
- IPP extracted from "15035 -2 77 03 99 312 069"
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

# P.Code pattern: 1-3 uppercase letters (initials like "VS", "BAZ")
_PCODE_RE = re.compile(r'^[A-Z]{1,3}$')


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


def _is_nir_ipp_line(text: str) -> bool:
    """
    Detect NIR-like lines: '78950 -2 06 12 99 622 925' or '15035 -2 77 03 99 312 069'
    These start with 4-6 digits followed by space-dash pattern.
    Must NOT be classified as fse_number.
    """
    return bool(re.match(r'^\d{4,6}\s*[-]\s*\d', text.strip()))


def _is_fse_number(text: str) -> bool:
    """
    FSE/dossier number: standalone 5-6 digit number.
    Must NOT match NIR-like lines (which contain dashes after first digits).
    """
    stripped = text.strip()
    # Exclude NIR-like lines with dashes
    if _is_nir_ipp_line(stripped):
        return False
    # Must be purely numeric (5-6 digits standalone)
    return bool(re.match(r'^\d{5,6}$', stripped))


def _extract_ipp_from_line(text: str) -> Optional[str]:
    """Extract IPP from '15035 -2 77 03 99 312 069' → '15035'"""
    match = re.match(r'^(\d{4,6})\s*[\-\s]', text.strip())
    if match:
        return match.group(1)
    return None


def _is_prescripteur_line(text: str) -> bool:
    t = text.lower()
    return bool(re.search(r'presc[ri]*[pb]?teur', t))


def _is_operateur_line(text: str) -> bool:
    t = text.lower()
    return bool(re.search(r'op[eé]rateur', t))


def _is_prescriber_line(text: str) -> bool:
    return _is_prescripteur_line(text) or _is_operateur_line(text)


def _is_practitioner_line(text: str) -> bool:
    t = text.lower()
    return 'orthoptiste' in t or 'orhoptiste' in t


def _is_establishment(text: str) -> bool:
    t = text.upper()
    return 'CDS ' in t or 'OPHTALMOLOGIE' in t or 'CENTRE DE SOINS' in t


def _is_montant(text: str) -> bool:
    return bool(re.search(r'\d+[,\.]\d{2}\s*€?$', text))


def _is_uppercase_name(text: str) -> bool:
    t = text.strip()
    return bool(re.match(r'^[A-ZÉÈÊËÀÂÄÙÛÜÔÖÎÏÇ][A-ZÉÈÊËÀÂÄÙÛÜÔÖÎÏÇ\-]{2,}$', t))


def _extract_name_after_colon(text: str) -> str:
    m = re.search(r'(?:op[eé]rateur|prescripteur)\s*:?\s*', text, re.IGNORECASE)
    if not m:
        return text.strip()

    after = text[m.end():].strip()
    name_chars = []
    for ch in after:
        if ch.isupper() or ch in ' ,-':
            name_chars.append(ch)
        elif ch == '\n':
            break
        else:
            break

    name = ''.join(name_chars).strip(' ,')
    name = re.sub(r'\s+[A-Z]$', '', name).strip(' ,')

    # If only a P.Code (1-3 letters like "VS") → return empty, look at next line
    if _PCODE_RE.match(name):
        return ""

    return name


def _extract_prescriber_from_amount_line(text: str) -> Optional[str]:
    match = re.search(r'[@€]\s*([A-ZÉÈÊËÀÂÄÙÛÜÔÖÎÏÇ][A-ZÉÈÊËÀÂÄÙÛÜÔÖÎÏÇ\s\-]{2,})$', text.strip())
    if match:
        return match.group(1).strip()
    return None


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
    if _is_nir_ipp_line(text):
        return "nir_ipp"   # NIR-like line — skip as fse_number
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
        "prescriber":   None,
        "operateur":    None,
        "practitioner": None,
        "establishment": None,
        "rpps":         None,
        "nir":          None,
        "ipp":          None,
        "amy_codes":    [],
        "dates":        [],
        "fse_number":   None,
        "montant":      None,
    }

    all_texts = [item.get("text", "") for item in ocr_results]

    for idx, item in enumerate(ocr_results):
        text = item.get("text", "")
        conf = item.get("confidence", 0)

        # ── PRE-FILTER ────────────────────────────────────────────────────────

        # Prescripteur → real doctor
        if _is_prescripteur_line(text) and fields["prescriber"] is None:
            name = _extract_name_after_colon(text)
            if name:
                fields["prescriber"] = name
            else:
                # P.Code only → look at next non-empty line
                next_idx = idx + 1
                while next_idx < len(all_texts):
                    next_text = all_texts[next_idx].strip()
                    if _is_uppercase_name(next_text):
                        fields["prescriber"] = next_text
                        break
                    elif next_text:
                        break
                    next_idx += 1

        # Opérateur → fallback
        if _is_operateur_line(text) and fields["operateur"] is None:
            name = _extract_name_after_colon(text)
            if name:
                fields["operateur"] = name

        # Prescriber from amount+name merged line
        prescriber_from_amount = _extract_prescriber_from_amount_line(text)
        if prescriber_from_amount and fields["prescriber"] is None:
            fields["prescriber"] = prescriber_from_amount

        # IPP from NIR-like line
        ipp_extracted = _extract_ipp_from_line(text)
        if ipp_extracted and fields["ipp"] is None:
            fields["ipp"] = ipp_extracted

        # RPPS
        rpps_extracted = _extract_rpps_from_line(text)
        if rpps_extracted and fields["rpps"] is None:
            fields["rpps"] = rpps_extracted

        # Dates
        if _is_date(text):
            for d in re.findall(r'\d{2}/\d{2}/\d{4}', text):
                if d not in fields["dates"]:
                    fields["dates"].append(d)

        # ── Noise filter ──────────────────────────────────────────────────────
        if is_noise(text, conf):
            continue

        field_type = classify_field(text)
        entry = {"text": text, "confidence": conf}
        if field_type:
            entry["field"] = field_type
        relevant.append(entry)

        # ── Populate fields ───────────────────────────────────────────────────
        if field_type == "amy_code":
            fields["amy_codes"].append(text)

        elif field_type == "prescriber":
            if _is_prescripteur_line(text) and fields["prescriber"] is None:
                fields["prescriber"] = _extract_name_after_colon(text)
            elif _is_operateur_line(text) and fields["operateur"] is None:
                fields["operateur"] = _extract_name_after_colon(text)

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

        elif field_type == "nir_ipp":
            pass  # Already handled in pre-filter (IPP extraction)

        elif field_type == "date":
            for d in re.findall(r'\d{2}/\d{2}/\d{4}', text):
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

    # ── Final: Opérateur fallback ─────────────────────────────────────────────
    if fields["prescriber"] is None and fields["operateur"]:
        fields["prescriber"] = fields["operateur"]

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