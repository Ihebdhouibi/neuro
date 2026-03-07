#!/usr/bin/env python3
"""
Prescription Generator Module
Handles PDF prescription generation, EDM storage, and thumbnail creation
"""

import os
import re
from pathlib import Path
from typing import Optional, Dict, Tuple
from datetime import datetime
import fitz  # PyMuPDF
from PIL import Image
from loguru import logger

# Official AMY Procedure Table
AMY_TABLE: Dict[str, Dict[str, str]] = {
    'AMY 8': {
        'label': 'Mesure de l\'acuité visuelle et de la réfraction – Renouvellement',
        'price': '20,80 €'
    },
    'AMY 15': {
        'label': 'Bilan des troubles oculomoteurs',
        'price': '39,00 €'
    },
    'AMY 7,7': {
        'label': 'Séance orthoptique (courte)',
        'price': '15,40 €'
    },
    'AMY 7': {
        'label': 'Traitement de l\'amblyopie par série de vingt séances',
        'price': '18,20 €'
    },
    'AMY 4': {
        'label': 'Traitement des hétérophories (20 séances)',
        'price': '10,40 €'
    },
    'AMY 7.7': {
        'label': 'Traitement du strabisme par série de vingt séances',
        'price': '20,02 €'
    },
}

# Prescribers Table (from appendix 1 - selected by P.Code initials)
PRESCRIBERS_TABLE: Dict[str, Dict[str, str]] = {
    'DM': {
        'name': 'Dr. Martin',
        'rpps': 'RPPS-123456'
    },
    'DL': {
        'name': 'Dr. Leroy',
        'rpps': 'RPPS-987654'
    },
}


def normalize_amy_code(raw: str) -> Optional[str]:
    """Normalize AMY code from OCR text (e.g., 'AMY (8)' -> 'AMY 8')"""
    if not raw:
        return None
    # Match patterns like "AMY (8)", "AMY 8", "AMY8", etc.
    match = re.search(r'AMY\s*\(?\s*(\d+(?:[,\.]\d+)?)\s*\)?', raw, re.IGNORECASE)
    if not match:
        return None
    num = match.group(1).replace('.', ',')
    return f'AMY {num}'


def search_amy_table(amy_code: str) -> Optional[Dict[str, str]]:
    """Search the official AMY table for procedure information"""
    normalized = normalize_amy_code(amy_code)
    if not normalized:
        return None
    return AMY_TABLE.get(normalized)


def get_prescriber_by_initials(initials: str) -> Optional[Dict[str, str]]:
    """Get prescriber information by initials (P.Code)"""
    return PRESCRIBERS_TABLE.get(initials.upper())


def compute_edm_path(base_path: str, ipp: str) -> str:
    """
    Compute EDM directory path from IPP number.
    Example: 15035 -> D:\Stimut\Documents_Patients\00\00\00\15\03\5
    The number is read from right to left in pairs.
    """
    # Remove all non-digits
    cleaned = re.sub(r'\D', '', ipp)
    if not cleaned:
        return base_path
    
    parts = []
    i = len(cleaned)
    # Read from right to left in pairs
    while i > 0:
        start = max(0, i - 2)
        part = cleaned[start:i] or '00'
        parts.insert(0, part)
        i -= 2
    
    # Pad to 6 directories (12 digits max)
    while len(parts) < 6:
        parts.insert(0, '00')
    
    return os.path.join(base_path, *parts)


def build_prescription_filename(finess: str, fse_number: str) -> str:
    """Build prescription filename: Prescription_Finess_FSE no.pdf"""
    return f'Prescription_{finess}_FSE {fse_number}.pdf'


def create_pdf_prescription(
    template_path: Optional[str],
    patient_info: Dict[str, str],
    prescriber_info: Dict[str, str],
    amy_procedure: Dict[str, str],
    finess: str,
    fse_number: str,
    output_path: str
) -> str:
    """
    Create PDF prescription from template or generate new one.
    
    Args:
        template_path: Path to center-specific template (optional)
        patient_info: {lastName, firstName, ssn, ipp}
        prescriber_info: {name, rpps}
        amy_procedure: {code, label, price}
        finess: Center FINESS number
        fse_number: FSE number
        output_path: Full path where PDF should be saved
    
    Returns:
        Path to created PDF
    """
    # Create a new PDF document
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)  # A4 size
    
    # If template exists, load it
    if template_path and os.path.exists(template_path):
        template_doc = fitz.open(template_path)
        if len(template_doc) > 0:
            page = doc.new_page(width=template_doc[0].rect.width, height=template_doc[0].rect.height)
            page.show_pdf_page(page.rect, template_doc, 0)
        template_doc.close()
    
    # Define positions and fonts
    font_size_title = 16
    font_size_header = 12
    font_size_body = 10
    font_size_footer = 8
    
    margin = 50
    y_pos = margin
    
    # Title
    page.insert_text(
        (margin, y_pos),
        "PRESCRIPTION ORTHOPTIQUE",
        fontsize=font_size_title,
        color=(0, 0, 0),
        fontname="helv"
    )
    y_pos += 30
    
    # Date
    current_date = datetime.now().strftime("%d/%m/%Y")
    page.insert_text(
        (margin, y_pos),
        f"Date: {current_date}",
        fontsize=font_size_body,
        color=(0, 0, 0),
        fontname="helv"
    )
    y_pos += 40
    
    # Patient Information
    page.insert_text(
        (margin, y_pos),
        "PATIENT:",
        fontsize=font_size_header,
        color=(0, 0, 0),
        fontname="helv"
    )
    y_pos += 20
    
    page.insert_text(
        (margin + 20, y_pos),
        f"Nom: {patient_info.get('lastName', '')}",
        fontsize=font_size_body,
        color=(0, 0, 0),
        fontname="helv"
    )
    y_pos += 15
    
    page.insert_text(
        (margin + 20, y_pos),
        f"Prénom: {patient_info.get('firstName', '')}",
        fontsize=font_size_body,
        color=(0, 0, 0),
        fontname="helv"
    )
    y_pos += 15
    
    page.insert_text(
        (margin + 20, y_pos),
        f"N° Sécurité Sociale: {patient_info.get('ssn', '')}",
        fontsize=font_size_body,
        color=(0, 0, 0),
        fontname="helv"
    )
    y_pos += 15
    
    page.insert_text(
        (margin + 20, y_pos),
        f"IPP (N° dossier): {patient_info.get('ipp', '')}",
        fontsize=font_size_body,
        color=(0, 0, 0),
        fontname="helv"
    )
    y_pos += 40
    
    # Prescriber Information
    page.insert_text(
        (margin, y_pos),
        "PRESCRIPTEUR:",
        fontsize=font_size_header,
        color=(0, 0, 0),
        fontname="helv"
    )
    y_pos += 20
    
    page.insert_text(
        (margin + 20, y_pos),
        f"Nom: {prescriber_info.get('name', '')}",
        fontsize=font_size_body,
        color=(0, 0, 0),
        fontname="helv"
    )
    y_pos += 15
    
    page.insert_text(
        (margin + 20, y_pos),
        f"RPPS: {prescriber_info.get('rpps', '')}",
        fontsize=font_size_body,
        color=(0, 0, 0),
        fontname="helv"
    )
    y_pos += 40
    
    # Procedure Information
    page.insert_text(
        (margin, y_pos),
        "PROCÉDURE:",
        fontsize=font_size_header,
        color=(0, 0, 0),
        fontname="helv"
    )
    y_pos += 20
    
    page.insert_text(
        (margin + 20, y_pos),
        f"Code: {amy_procedure.get('code', '')}",
        fontsize=font_size_body,
        color=(0, 0, 0),
        fontname="helv"
    )
    y_pos += 15
    
    page.insert_text(
        (margin + 20, y_pos),
        f"Libellé: {amy_procedure.get('label', '')}",
        fontsize=font_size_body,
        color=(0, 0, 0),
        fontname="helv"
    )
    y_pos += 15
    
    page.insert_text(
        (margin + 20, y_pos),
        f"Montant: {amy_procedure.get('price', '')}",
        fontsize=font_size_body,
        color=(0, 0, 0),
        fontname="helv"
    )
    y_pos += 40
    
    # Footer with FSE and FINESS
    page.insert_text(
        (margin, 800),
        f"FSE N°: {fse_number} | FINESS: {finess}",
        fontsize=font_size_footer,
        color=(0.5, 0.5, 0.5),
        fontname="helv"
    )
    
    # Add stamp and signature area (pre-filled placeholder)
    y_pos = 700
    page.insert_text(
        (margin, y_pos),
        "Cachet et signature:",
        fontsize=font_size_body,
        color=(0, 0, 0),
        fontname="helv"
    )
    y_pos += 30
    
    # Draw signature line
    page.draw_line(
        (margin + 20, y_pos),
        (margin + 200, y_pos),
        color=(0, 0, 0),
        width=1
    )
    
    # Save PDF
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    doc.save(output_path)
    doc.close()
    
    logger.info(f"Prescription PDF created: {output_path}")
    return output_path


def create_thumbnail(pdf_path: str, thumbnail_path: str, max_size: Tuple[int, int] = (700, 700)) -> str:
    """
    Create thumbnail from PDF (JPG format, approximately 500-700 KB).
    
    Args:
        pdf_path: Path to PDF file
        thumbnail_path: Output path for thumbnail
        max_size: Maximum dimensions (width, height)
    
    Returns:
        Path to created thumbnail
    """
    try:
        # Open PDF and render first page
        doc = fitz.open(pdf_path)
        if len(doc) == 0:
            raise ValueError("PDF has no pages")
        
        page = doc[0]
        # Render at 150 DPI for good quality
        mat = fitz.Matrix(150/72, 150/72)
        pix = page.get_pixmap(matrix=mat)
        
        # Convert to PIL Image
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        
        # Resize to fit max_size while maintaining aspect ratio
        img.thumbnail(max_size, Image.Resampling.LANCZOS)
        
        # Save as JPG with quality to target ~500-700 KB
        os.makedirs(os.path.dirname(thumbnail_path), exist_ok=True)
        
        # Adjust quality to target file size
        quality = 85
        img.save(thumbnail_path, "JPEG", quality=quality, optimize=True)
        
        # Check file size and adjust if needed
        file_size = os.path.getsize(thumbnail_path)
        target_size = 600 * 1024  # 600 KB target
        
        if file_size > target_size * 1.2:  # If too large
            quality = 70
            img.save(thumbnail_path, "JPEG", quality=quality, optimize=True)
        elif file_size < target_size * 0.5:  # If too small
            quality = 95
            img.save(thumbnail_path, "JPEG", quality=quality, optimize=True)
        
        doc.close()
        logger.info(f"Thumbnail created: {thumbnail_path} ({os.path.getsize(thumbnail_path) / 1024:.1f} KB)")
        return thumbnail_path
        
    except Exception as e:
        logger.error(f"Failed to create thumbnail: {e}")
        raise


def update_infopdf_file(patient_dir: str, pdf_filename: str, thumbnail_filename: str) -> bool:
    """
    Update infoPdf file in patient directory by adding a line.
    
    Args:
        patient_dir: Patient directory path
        pdf_filename: Name of PDF file
        thumbnail_filename: Name of thumbnail file
    
    Returns:
        True if successful
    """
    infopdf_path = os.path.join(patient_dir, 'infoPdf')
    
    try:
        # Create entry line (format may vary, using simple format)
        entry = f"{pdf_filename}|{thumbnail_filename}|{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        
        # Append to file (create if doesn't exist)
        with open(infopdf_path, 'a', encoding='utf-8') as f:
            f.write(entry)
        
        logger.info(f"Updated infoPdf file: {infopdf_path}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to update infoPdf file: {e}")
        return False


def generate_prescription(
    patient_info: Dict[str, str],
    prescriber_initials: str,
    amy_code: str,
    finess: str,
    fse_number: str,
    edm_base_path: str,
    template_path: Optional[str] = None
) -> Dict[str, str]:
    """
    Complete prescription generation workflow:
    1. Search AMY table
    2. Get prescriber info
    3. Generate PDF
    4. Save to EDM
    5. Create thumbnail
    6. Update infoPdf
    
    Returns:
        Dictionary with paths and status
    """
    try:
        # Step 1: Search AMY table
        amy_procedure = search_amy_table(amy_code)
        if not amy_procedure:
            raise ValueError(f"AMY code not found in table: {amy_code}")
        
        amy_procedure['code'] = normalize_amy_code(amy_code) or amy_code
        
        # Step 2: Get prescriber info
        prescriber_info = get_prescriber_by_initials(prescriber_initials)
        if not prescriber_info:
            raise ValueError(f"Prescriber not found: {prescriber_initials}")
        
        # Step 3: Compute EDM path
        ipp = patient_info.get('ipp', '')
        if not ipp:
            raise ValueError("IPP number is required")
        
        edm_path = compute_edm_path(edm_base_path, ipp)
        os.makedirs(edm_path, exist_ok=True)
        
        # Step 4: Build filename and paths
        pdf_filename = build_prescription_filename(finess, fse_number)
        pdf_path = os.path.join(edm_path, pdf_filename)
        
        # Step 5: Create PDF
        create_pdf_prescription(
            template_path=template_path,
            patient_info=patient_info,
            prescriber_info=prescriber_info,
            amy_procedure=amy_procedure,
            finess=finess,
            fse_number=fse_number,
            output_path=pdf_path
        )
        
        # Step 6: Create thumbnail directory
        thumbnail_dir = os.path.join(edm_path, 'thumbnails')
        os.makedirs(thumbnail_dir, exist_ok=True)
        
        thumbnail_filename = pdf_filename.replace('.pdf', '.jpg')
        thumbnail_path = os.path.join(thumbnail_dir, thumbnail_filename)
        
        # Step 7: Create thumbnail
        create_thumbnail(pdf_path, thumbnail_path)
        
        # Step 8: Update infoPdf
        update_infopdf_file(edm_path, pdf_filename, thumbnail_filename)
        
        return {
            'success': True,
            'pdf_path': pdf_path,
            'thumbnail_path': thumbnail_path,
            'edm_path': edm_path,
            'pdf_filename': pdf_filename,
            'thumbnail_filename': thumbnail_filename
        }
        
    except Exception as e:
        logger.error(f"Prescription generation failed: {e}")
        return {
            'success': False,
            'error': str(e)
        }


