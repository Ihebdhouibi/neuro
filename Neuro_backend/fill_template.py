#!/usr/bin/env python3
"""
Word Prescription Template Filler - FIXED paragraph indices
P[0]:  Nom du centre
P[2]:  Adresse / Tél / Email
P[4]:  FINESS + Fait à
P[5]:  Date DD / MM / YYYY
P[8]:  Nom / Prénom
P[9]:  NIR
P[10]: Date de naissance
P[12]: Docteur / RPPS
P[14]: Les soins orthoptiques suivants
P[15]: ACTES PRESCRITS
P[16-25]: Actes (slots vides)
"""

import os
import copy
import shutil
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime
import re

from docx import Document
from docx.shared import Pt, RGBColor
from loguru import logger

DEFAULT_TEMPLATE = Path(__file__).parent / "templates" / "prescription" / "Ordonnance_Template vierge.docx"

AMY_TABLE: Dict[str, Dict[str, str]] = {
    'AMY 8':    {'label': "Mesure de l'acuité visuelle et de la réfraction – Renouvellement", 'price': '20,80 €'},
    'AMY 15':   {'label': 'Bilan des troubles oculomoteurs', 'price': '39,00 €'},
    'AMY 7,7':  {'label': 'Séance orthoptique (courte)', 'price': '15,40 €'},
    'AMY 7':    {'label': "Traitement de l'amblyopie par série de vingt séances", 'price': '18,20 €'},
    'AMY 4':    {'label': 'Traitement des hétérophories (20 séances)', 'price': '10,40 €'},
    'AMY 7.7':  {'label': 'Traitement du strabisme par série de vingt séances', 'price': '20,02 €'},
    'AMY 30':   {'label': 'Bilan orthoptique des déficiences visuelles (basse vision)', 'price': '78,00 €'},
    'AMY 30,5': {'label': 'Bilan des conséquences neuro-ophtalmologiques', 'price': '79,30 €'},
    'AMY 10':   {'label': 'Bilan des déséquilibres de la vision binoculaire', 'price': '26,00 €'},
    'AMY 14,5': {'label': 'Bilan des déséquilibres avec trouble neurosensoriel/accommodatif', 'price': '37,70 €'},
    'AMY 15,5': {'label': "Bilan d'une amblyopie", 'price': '40,30 €'},
    'AMY 19,2': {'label': 'Rééducation déficience visuelle - Plus de 16 ans (45 mn)', 'price': '49,92 €'},
    'AMY 13,2': {'label': 'Rééducation déficience visuelle - 16 ans et moins (30 mn)', 'price': '34,32 €'},
    'AMY 8,7':  {'label': 'Mesure acuité visuelle et réfraction - Primo-prescription', 'price': '22,62 €'},
}


def normalize_amy_code(raw: str) -> Optional[str]:
    if not raw:
        return None
    match = re.search(r'AMY\s*\(?\s*(\d+(?:[,\.]\d+)?)\s*\)?', raw, re.IGNORECASE)
    if not match:
        return None
    num = match.group(1).replace('.', ',')
    return f'AMY {num}'


def _format_date_fr(iso_date: Optional[str]) -> str:
    if not iso_date:
        return ""
    try:
        dt = datetime.strptime(iso_date, "%Y-%m-%d")
        return dt.strftime("%d/%m/%Y")
    except ValueError:
        return iso_date


def _insert_acts(doc, acts_with_labels: List[Dict[str, str]]):
    """Insert acts into slots P[16] to P[25]"""
    actes_idx = None
    for i, p in enumerate(doc.paragraphs):
        if 'ACTES PRESCRITS' in p.text:
            actes_idx = i
            break
    if actes_idx is None:
        return
    for j, act in enumerate(acts_with_labels):
        target_idx = actes_idx + 1 + j
        if target_idx >= len(doc.paragraphs):
            break
        p = doc.paragraphs[target_idx]
        for run in p.runs:
            run.text = ""
        run = p.add_run(f"- {act['code']} : {act['label']}    ({act['price']})")
        run.font.size = Pt(11)
        run.font.color.rgb = RGBColor(0x33, 0x33, 0x33)


def fill_prescription_template(
    extraction_data: Dict,
    center_info: Optional[Dict[str, str]] = None,
    finess: str = "",
    city: str = "",
    amy_table: Optional[Dict[str, Dict[str, str]]] = None,
    template_path: Optional[str] = None,
) -> str:

    tpl = Path(template_path) if template_path else DEFAULT_TEMPLATE
    if not tpl.exists():
        raise FileNotFoundError(f"Template not found: {tpl}")

    doc = Document(str(tpl))
    paras = doc.paragraphs

    patient   = extraction_data.get("patient", {})
    doctor    = extraction_data.get("doctor", {})
    care      = extraction_data.get("orthoptic_care", {})
    form_date = _format_date_fr(extraction_data.get("form_date"))

    # --- P[0]: Centre name ---
    if center_info and center_info.get("name"):
        for run in paras[0].runs:
            if "Nom du centre" in run.text or run.text.strip():
                run.text = center_info["name"]
                break

    # --- P[2]: Adresse / Tél / Email ---
    if center_info:
        p2 = paras[2]
        for run in p2.runs:
            if "Adresse" in run.text:
                run.text = f"Adresse\u00a0: {center_info.get('address', '')}"
            elif "Tél" in run.text:
                run.text = f"\nTél : {center_info.get('tel', '')}"
            elif "Email" in run.text:
                run.text = f"\nEmail : {center_info.get('email', '')}"

    # --- P[4]: FINESS + Fait à ---
    p4 = paras[4]
    for run in p4.runs:
        if "FINESS" in run.text:
            run.text = f"FINESS : {finess}"
        elif "Fait à" in run.text:
            run.text = f"Fait à {city}"

    # --- P[5]: Date ____ / ____ / ________ ---
    if form_date:
        parts = form_date.split("/")
        if len(parts) == 3:
            p5 = paras[5]
            runs = p5.runs
            # runs: [0]='Date : ' [1]='____ ' [2]=' / ' [3]='____ ' [4]=' / ' [5]='________'
            if len(runs) >= 6:
                runs[1].text = parts[0]   # day
                runs[3].text = parts[1]   # month
                runs[5].text = parts[2]   # year

    # --- P[8]: Nom / Prénom ---
    last_name  = patient.get("last_name") or ""
    first_name = patient.get("first_name") or ""
    p8 = paras[8]
    for run in p8.runs:
        if "Nom :" in run.text:
            run.text = f"Nom : {last_name}"
        elif "Prénom :" in run.text:
            run.text = f"Prénom : {first_name}"

    # --- P[9]: NIR ---
    nir = patient.get("nir") or ""
    p9 = paras[9]
    for run in p9.runs:
        if "Sécurité Sociale" in run.text:
            run.text = f"N° Sécurité Sociale (NIR) : {nir}"
            break

    # --- P[10]: Date de naissance ---
    birth = _format_date_fr(patient.get("birth_date"))
    p10 = paras[10]
    for run in p10.runs:
        if "Date de naissance" in run.text:
            run.text = f"Date de naissance : {birth}"
            break

    # --- P[12]: Docteur / RPPS ---
    doc_name = doctor.get("full_name") or ""
    rpps     = doctor.get("rpps") or ""
    p12 = paras[12]
    for run in p12.runs:
        if "Docteur :" in run.text:
            run.text = f"Je soussigné(e), Docteur : {doc_name}"
        elif run.text.strip() == " : " and p12.runs.index(run) > 0:
            prev = p12.runs[p12.runs.index(run) - 1]
            if "RPPS" in prev.text:
                run.text = f" : {rpps}"

    # --- P[14]: Les soins orthoptiques ---
    description = care.get("description") or ""
    p14 = paras[14]
    for run in p14.runs:
        if "soins orthoptiques" in run.text:
            run.text = f"Les soins orthoptiques suivants : {description}"
            break

    # --- P[16+]: Actes prescrits ---
    acts_raw = care.get("acts_prescribed", [])
    if acts_raw:
        lookup = amy_table if amy_table is not None else AMY_TABLE
        acts_with_labels = []
        for code in acts_raw:
            normalized = normalize_amy_code(code) or code
            info = lookup.get(normalized, {})
            acts_with_labels.append({
                "code": normalized,
                "label": info.get("label", ""),
                "price": info.get("price", ""),
            })
        _insert_acts(doc, acts_with_labels)
    # --- P[28]: Cachet + Signature ---
    p28 = paras[28]
    cachet_text = ""
    if center_info:
        cachet_text = (
            f"{center_info.get('name', '')}\n"
            f"FINESS: {finess}\n"
            f"{center_info.get('address', '')}\n"
            f"Tél: {center_info.get('tel', '')}"
        )
    signature_text = doc_name if doc_name else ""

    for run in p28.runs:
        if "Cachet du centre" in run.text:
            run.text = f"Cachet du centre\n{cachet_text}"
        elif "Signature du prescripteur" in run.text:
            run.text = f"Signature du prescripteur\n{signature_text}"
    # --- Save ---
    output_dir = Path(tpl).parent / "filled"
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filled_path = output_dir / f"Ordonnance_filled_{timestamp}.docx"
    doc.save(str(filled_path))
    logger.info(f"Filled template saved: {filled_path}")
    return str(filled_path)


def fill_and_convert_to_pdf(
    extraction_data: Dict,
    output_pdf_path: str,
    center_info: Optional[Dict[str, str]] = None,
    finess: str = "",
    city: str = "",
    amy_table: Optional[Dict[str, Dict[str, str]]] = None,
    template_path: Optional[str] = None,
) -> str:

    filled_docx = fill_prescription_template(
        extraction_data=extraction_data,
        center_info=center_info,
        finess=finess,
        city=city,
        amy_table=amy_table,
        template_path=template_path,
    )

    os.makedirs(os.path.dirname(output_pdf_path), exist_ok=True)

    try:
        from docx2pdf import convert
        convert(filled_docx, output_pdf_path)
        logger.info(f"PDF generated: {output_pdf_path}")
    except Exception as e:
        logger.error(f"docx2pdf conversion failed: {e}")
        raise

    try:
        os.unlink(filled_docx)
    except OSError:
        pass

    return output_pdf_path
