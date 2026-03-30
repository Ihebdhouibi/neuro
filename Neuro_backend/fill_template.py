#!/usr/bin/env python3
"""
Word Prescription Template Filler - FIXED paragraph indices
P[0]:  Nom du centre
P[1]:  Logo (image PNG)
P[2]:  Adresse / Tél / Email
P[4]:  FINESS + Fait à
P[5]:  Date DD / MM / YYYY
P[8]:  Nom / Prénom
P[9]:  NIR
P[10]: Date de naissance
P[12]: Docteur / RPPS  runs: [0]='Je soussigné(e), Docteur : ' [1]='spaces' [2]='RPPS' [3]=' : '
P[14]: Les soins orthoptiques suivants
P[15]: ACTES PRESCRITS
P[16-25]: Actes (slots vides)
P[28]: Cachet (image PNG) + Signature (image PNG) — tableau 2 colonnes
"""

import os
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime
import re
import copy

from docx import Document
from docx.shared import Pt, RGBColor, Inches, Cm
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from loguru import logger

DEFAULT_TEMPLATE      = Path(__file__).parent / "templates" / "prescription" / "Ordonnance_Template vierge.docx"
DEFAULT_CACHET_PNG    = Path(__file__).parent / "templates" / "prescription" / "cachet.png"
DEFAULT_SIGNATURE_PNG = Path(__file__).parent / "templates" / "prescription" / "signature.png"
DEFAULT_LOGO_PNG      = Path(__file__).parent / "templates" / "prescription" / "logo.png"

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


def _replace_p28_with_table(doc, p28, cachet_path: Optional[str], signature_path: Optional[str]):
    """Replace P[28] with borderless 1x2 table: Cachet | Signature"""
    tbl = doc.add_table(rows=1, cols=2)

    for cell in tbl.rows[0].cells:
        tc = cell._tc
        tcPr = tc.get_or_add_tcPr()
        tcBorders = OxmlElement('w:tcBorders')
        for border_name in ['top', 'left', 'bottom', 'right', 'insideH', 'insideV']:
            border = OxmlElement(f'w:{border_name}')
            border.set(qn('w:val'), 'nil')
            tcBorders.append(border)
        tcPr.append(tcBorders)

    for cell in tbl.rows[0].cells:
        cell.width = Cm(8)

    cell_left  = tbl.rows[0].cells[0]
    cell_right = tbl.rows[0].cells[1]

    p_left = cell_left.paragraphs[0]
    label_run = p_left.add_run("Cachet du centre\n")
    label_run.bold = True
    label_run.font.size = Pt(9)
    if cachet_path and Path(cachet_path).exists():
        try:
            p_left.add_run().add_picture(cachet_path, width=Inches(1.1))
        except Exception as e:
            logger.warning(f"Cachet error: {e}")
    else:
        p_left.add_run("[cachet manquant]")

    p_right = cell_right.paragraphs[0]
    label_run2 = p_right.add_run("Signature du prescripteur\n")
    label_run2.bold = True
    label_run2.font.size = Pt(9)
    if signature_path and Path(signature_path).exists():
        try:
            p_right.add_run().add_picture(signature_path, width=Inches(1.1))
        except Exception as e:
            logger.warning(f"Signature error: {e}")
    else:
        p_right.add_run("[signature manquante]")

    p28._element.addnext(tbl._tbl)

    for run in p28.runs:
        run.text = ""
    p = p28._p
    for r in p.findall(qn('w:r')):
        p.remove(r)


def fill_prescription_template(
    extraction_data: Dict,
    center_info: Optional[Dict[str, str]] = None,
    finess: str = "",
    city: str = "",
    amy_table: Optional[Dict[str, Dict[str, str]]] = None,
    template_path: Optional[str] = None,
    cachet_png: Optional[str] = None,
    signature_png: Optional[str] = None,
    logo_png: Optional[str] = None,
) -> str:

    tpl = Path(template_path) if template_path else DEFAULT_TEMPLATE
    if not tpl.exists():
        raise FileNotFoundError(f"Template not found: {tpl}")

    cachet_path    = cachet_png    or (str(DEFAULT_CACHET_PNG)    if DEFAULT_CACHET_PNG.exists()    else None)
    signature_path = signature_png or (str(DEFAULT_SIGNATURE_PNG) if DEFAULT_SIGNATURE_PNG.exists() else None)
    logo_path      = logo_png      or (str(DEFAULT_LOGO_PNG)      if DEFAULT_LOGO_PNG.exists()      else None)

    doc   = Document(str(tpl))
    paras = doc.paragraphs

    patient   = extraction_data.get("patient", {})
    doctor    = extraction_data.get("doctor", {})
    care      = extraction_data.get("orthoptic_care", {})
    form_date = _format_date_fr(extraction_data.get("form_date"))

    # --- P[0]: Centre name ---
    if center_info and center_info.get("name"):
        for run in paras[0].runs:
            if run.text.strip():
                run.text = center_info["name"]
                break

    # --- P[1]: Logo ---
    if logo_path and Path(logo_path).exists():
        p1 = paras[1]
        # Clear existing runs
        for run in p1.runs:
            run.text = ""
        p = p1._p
        for r in p.findall(qn('w:r')):
            p.remove(r)
        # Insert logo image
        try:
            p1.add_run().add_picture(logo_path, width=Inches(1.0))
            logger.info(f"Logo inserted: {logo_path}")
        except Exception as e:
            logger.warning(f"Logo error: {e}")
    else:
        # Remove "logos" placeholder text
        for run in paras[1].runs:
            run.text = ""

    # --- P[2]: Adresse / Tél / Email ---
    if center_info:
        p2 = paras[2]
        for run in p2.runs:
            if "Adresse" in run.text:
                run.text = f"Adresse : {center_info.get('address', '')}"
            elif "Tél" in run.text or "T\u00e9l" in run.text:
                run.text = f"\nTél : {center_info.get('tel', '')}"
            elif "Email" in run.text:
                run.text = f"\nEmail : {center_info.get('email', '')}"

    # --- P[4]: FINESS + Fait à ---
    p4 = paras[4]
    for run in p4.runs:
        if "FINESS" in run.text:
            run.text = f"FINESS : {finess}"
        elif "Fait" in run.text:
            run.text = f"Fait à {city}"

    # --- P[5]: Date DD / MM / YYYY ---
    if form_date:
        parts = form_date.split("/")
        if len(parts) == 3:
            runs = paras[5].runs
            if len(runs) >= 6:
                runs[1].text = parts[0]
                runs[3].text = parts[1]
                runs[5].text = parts[2]

    # --- P[8]: Nom / Prénom ---
    last_name  = patient.get("last_name") or ""
    first_name = patient.get("first_name") or ""
    for run in paras[8].runs:
        if "Nom :" in run.text:
            run.text = f"Nom : {last_name}"
        elif "Prénom :" in run.text or "Pr\u00e9nom :" in run.text:
            run.text = f"Prénom : {first_name}"

    # --- P[9]: NIR ---
    nir = patient.get("nir") or ""
    for run in paras[9].runs:
        if "Sociale" in run.text or "NIR" in run.text:
            run.text = f"N° Sécurité Sociale (NIR) : {nir}"
            break

    # --- P[10]: Date de naissance ---
    birth = _format_date_fr(patient.get("birth_date"))
    for run in paras[10].runs:
        if "naissance" in run.text:
            run.text = f"Date de naissance : {birth}"
            break

    # --- P[12]: Docteur / RPPS ---
    # runs: [0]='Je soussigné(e), Docteur : ' [1]='     ' [2]='RPPS' [3]=' : '
    doc_name = doctor.get("full_name") or ""
    doc_name = re.sub(r'\s+[A-Z]$', '', doc_name).strip(' ,')
    rpps = doctor.get("rpps") or ""
    p12_runs = paras[12].runs
    if len(p12_runs) >= 4:
        p12_runs[0].text = f"Je soussigné(e), Docteur : {doc_name}"
        p12_runs[1].text = "     "
        p12_runs[2].text = "RPPS"
        p12_runs[3].text = f" : {rpps}"
    else:
        for run in paras[12].runs:
            if "Docteur" in run.text:
                run.text = f"Je soussigné(e), Docteur : {doc_name}"
            elif "RPPS" in run.text:
                run.text = f"RPPS : {rpps}"

    # --- P[14]: Les soins orthoptiques ---
    description = care.get("description") or ""
    for run in paras[14].runs:
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
    _replace_p28_with_table(doc, paras[28], cachet_path, signature_path)

    # --- Save ---
    output_dir = Path(tpl).parent / "filled"
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp  = datetime.now().strftime("%Y%m%d_%H%M%S")
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
    cachet_png: Optional[str] = None,
    signature_png: Optional[str] = None,
    logo_png: Optional[str] = None,
) -> str:

    filled_docx = fill_prescription_template(
        extraction_data=extraction_data,
        center_info=center_info,
        finess=finess,
        city=city,
        amy_table=amy_table,
        template_path=template_path,
        cachet_png=cachet_png,
        signature_png=signature_png,
        logo_png=logo_png,
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