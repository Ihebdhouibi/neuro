#!/usr/bin/env python3
"""
Test: Fill the prescription Word template with data derived from
real OCR output (video_analysis/analysis_data.json) and produce a PDF.

This tests the prescription generation flow in isolation, without
needing the actual FSE software or a live OCR pipeline.
"""
import os, sys
sys.path.insert(0, os.path.dirname(__file__))

from fill_template import fill_prescription_template, fill_and_convert_to_pdf

# ---------------------------------------------------------------------------
# Extraction data modeled after real OCR from video_analysis/analysis_data.json
# Patient: TESTIDEM (TEST IDEM), AMY codes: AMY8, AMY8.5+6, date: 30/09/2025
# Mapped into the openai_extraction schema (sample_schema.json)
# ---------------------------------------------------------------------------
real_extraction = {
    "form_date": "2025-09-30",
    "patient": {
        "last_name": "TESTIDEM",
        "first_name": "IDEM",
        "nir": "1 75 01 75 049 001 23",
        "birth_date": "1975-01-15"
    },
    "doctor": {
        "full_name": "Dr. CHAVANNES",
        "rpps": "10003456789"
    },
    "orthoptic_care": {
        "description": "Bilan orthoptique et mesure acuité visuelle",
        "acts_prescribed": ["AMY 8", "AMY 15"]
    },
    "ocr_raw_text": "raw OCR text from video frame..."
}

# Center info — matches client center (FINESS 920036563, Nanterre)
center_info = {
    "name": "CDS OPHTALMOLOGIE NANTERRE LA BOULE",
    "address": "123 Avenue de la République, 92000 Nanterre",
    "tel": "01 47 00 00 00",
    "email": "contact@cds-nanterre.fr"
}

FINESS = "920036563"
CITY = "Nanterre"

# ============================
# Test 1: Fill template → docx
# ============================
print("=" * 60)
print("TEST 1: Fill Word template (docx only)")
print("=" * 60)
filled = fill_prescription_template(
    extraction_data=real_extraction,
    center_info=center_info,
    finess=FINESS,
    city=CITY,
)
print(f"  Filled docx : {filled}")
print(f"  Exists      : {os.path.exists(filled)}")
print(f"  Size        : {os.path.getsize(filled)} bytes")

# Quick verification: re-read the filled doc and print field values
from docx import Document
doc = Document(filled)
print("\n  --- Filled content verification ---")
for i, p in enumerate(doc.paragraphs):
    text = p.text.strip()
    if text:
        print(f"  P[{i:>2}]: {text}")

# ============================
# Test 2: Fill + convert to PDF
# ============================
print("\n" + "=" * 60)
print("TEST 2: Fill Word template + convert to PDF")
print("=" * 60)
pdf_out = os.path.join(
    os.path.dirname(__file__),
    "templates", "prescription", "filled",
    f"Prescription_{FINESS}_FSE 553381.pdf"
)
try:
    pdf = fill_and_convert_to_pdf(
        extraction_data=real_extraction,
        output_pdf_path=pdf_out,
        center_info=center_info,
        finess=FINESS,
        city=CITY,
    )
    print(f"  PDF created : {pdf}")
    print(f"  Exists      : {os.path.exists(pdf)}")
    print(f"  Size        : {os.path.getsize(pdf)} bytes")
except Exception as e:
    print(f"  PDF conversion failed: {e}")
    print("  (docx2pdf requires Microsoft Word installed on the machine)")

print("\nDone!")
