#!/usr/bin/env python3
"""
FSE OCR API - FastAPI Backend with PaddleOCR
Simplified version for window capture screenshot processing
"""

import os
import tempfile
from typing import Optional
from pathlib import Path
import asyncio
from contextlib import asynccontextmanager
from dotenv import load_dotenv

load_dotenv(r"C:/Users/hp/Downloads/neuro/Neuro_backend/.env")

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from tempfile import gettempdir
from loguru import logger
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database import init_db, close_db

# ── Center config from .env ──────────────────────────────────────────────────
def get_center_info() -> dict:
    return {
        "name":    os.getenv("CENTER_NAME",    "CDS OPHTALMOLOGIE NANTERRE LA BOULE"),
        "address": os.getenv("CENTER_ADDRESS", "123 Avenue de la République, 92000 Nanterre"),
        "tel":     os.getenv("CENTER_TEL",     "01 47 00 00 00"),
        "email":   os.getenv("CENTER_EMAIL",   "contact@cds-nanterre.fr"),
    }

CENTER_FINESS = os.getenv("CENTER_FINESS", "920036563")
CENTER_CITY   = os.getenv("CENTER_CITY",   "Nanterre")
EDM_BASE_PATH = os.getenv("EDM_BASE_PATH", "C:/temp/fse_ocr")

# ── Pydantic models ──────────────────────────────────────────────────────────
class ParseResponse(BaseModel):
    success: bool
    message: str
    content: Optional[str] = None
    extract: Optional[dict] = None

class PrescriptionRequest(BaseModel):
    patient: dict
    prescriber_initials: str
    amy_code: str
    finess: str
    fse_number: str
    edm_base_path: str
    template_path: Optional[str] = None

class PrescriptionResponse(BaseModel):
    success: bool
    message: str
    pdf_path: Optional[str] = None
    thumbnail_path: Optional[str] = None
    edm_path: Optional[str] = None
    error: Optional[str] = None

# ── OCR engine ───────────────────────────────────────────────────────────────
ocr_engine = None

def initialize_ocr():
    global ocr_engine
    if ocr_engine is None:
        try:
            from paddleocr import PaddleOCR
            ocr_engine = PaddleOCR(
                use_angle_cls=True,
                lang='fr',
                use_gpu=False,
                show_log=False
            )
            logger.info("✅ PaddleOCR initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize PaddleOCR: {e}")
            raise
    return ocr_engine

# ── Lifespan ─────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        await init_db()
        logger.info("✅ Database initialized successfully")
    except Exception as e:
        logger.warning(f"⚠️ Database initialization failed: {e}")

    try:
        initialize_ocr()
    except Exception as e:
        logger.warning(f"⚠️ Failed to initialize OCR: {e}")
        logger.warning("⚠️ OCR features will be disabled")

    yield

    try:
        await close_db()
    except Exception as e:
        logger.warning(f"⚠️ Error closing database: {e}")
    logger.info("🔄 Application shutdown complete")

# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="FSE OCR API",
    description="OCR API for French medical prescription processing using PaddleOCR",
    version="2.0.0",
    lifespan=lifespan
)

cors_origins = os.getenv("CORS_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins if cors_origins != ["*"] else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from api.routes import router as db_router
app.include_router(db_router)

from api.auth import router as auth_router
app.include_router(auth_router)

temp_dir = os.getenv("TMPDIR", gettempdir())
os.makedirs(temp_dir, exist_ok=True)
app.mount("/static", StaticFiles(directory=temp_dir), name="static")

# ── OCR helpers ───────────────────────────────────────────────────────────────
def run_ocr_on_file(file_path: str, file_ext: str, unique_id: str):
    """Run PaddleOCR and return (lines, text, results_with_conf, image_path)"""
    image_path = None

    if file_ext == '.pdf':
        from pdf2image import convert_from_path
        images = convert_from_path(file_path, dpi=300)
        image_path = os.path.join(temp_dir, f"pdf_page_{unique_id}.jpg")
        images[0].save(image_path, 'JPEG')
        ocr_input = image_path
    else:
        ocr_input = file_path

    result = ocr_engine.ocr(ocr_input, cls=True)

    ocr_text_lines = []
    ocr_results_with_conf = []

    if result and result[0]:
        for line in result[0]:
            if line and len(line) >= 2:
                text = line[1][0]
                confidence = line[1][1]
                if confidence > 0.5:
                    ocr_text_lines.append(text)
                    ocr_results_with_conf.append({"text": text, "confidence": float(confidence)})

    ocr_text = "\n".join(ocr_text_lines)
    return ocr_text_lines, ocr_text, ocr_results_with_conf, image_path


def extract_schema_from_ocr(ocr_results_with_conf: list, ocr_text: str) -> dict:
    """Convert OCR results to schema using ocr_to_schema (no API needed)"""
    try:
        backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        sys.path.insert(0, backend_dir)
        from ocr_to_schema import extract_from_ocr_results
        result = extract_from_ocr_results(ocr_results_with_conf)
        logger.info("✅ OCR extraction completed (no API)")
        return result
    except Exception as e:
        logger.warning(f"⚠️ OCR extraction failed: {e}")
        return {"ocr_raw_text": ocr_text}


# ── Endpoints ─────────────────────────────────────────────────────────────────
@app.get("/")
async def root():
    return {
        "message": "FSE OCR API is running",
        "version": "2.0.0",
        "ocr_engine": "PaddleOCR",
        "center_finess": CENTER_FINESS,
        "center_city": CENTER_CITY,
    }


@app.post("/parse", response_model=ParseResponse)
async def parse_document(file: UploadFile = File(...)):
    """Image → OCR → structured JSON (no API key needed)"""
    try:
        if not ocr_engine:
            raise HTTPException(status_code=500, detail="OCR engine not initialized")

        allowed_extensions = {'.pdf', '.jpg', '.jpeg', '.png'}
        file_ext = Path(file.filename).suffix.lower() if file.filename else ''
        if file_ext not in allowed_extensions:
            raise HTTPException(status_code=400, detail=f"Unsupported file type: {file_ext}")

        content = await file.read()
        import uuid
        unique_id = str(uuid.uuid4())[:8]
        temp_path = os.path.join(temp_dir, f"upload_{unique_id}{file_ext}")

        with open(temp_path, 'wb') as f:
            f.write(content)

        image_path = None
        try:
            logger.info(f"Running PaddleOCR on {file.filename}")
            ocr_text_lines, ocr_text, ocr_results_with_conf, image_path = run_ocr_on_file(
                temp_path, file_ext, unique_id
            )
            logger.info(f"OCR extracted {len(ocr_text_lines)} lines")
            extract = extract_schema_from_ocr(ocr_results_with_conf, ocr_text)

            return ParseResponse(
                success=True,
                message="OCR processing completed successfully",
                content=ocr_text,
                extract=extract
            )
        finally:
            try:
                os.unlink(temp_path)
                if image_path and os.path.exists(image_path):
                    os.unlink(image_path)
            except Exception:
                pass

    except Exception as e:
        logger.error(f"Parsing failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Parsing failed: {str(e)}")


@app.post("/parse-and-generate", response_model=PrescriptionResponse)
async def parse_and_generate(
    file: UploadFile = File(...),
    finess: str = CENTER_FINESS,
    city: str = CENTER_CITY,
    edm_base_path: str = EDM_BASE_PATH,
):
    """
    Full pipeline: Image → OCR → JSON → fill_template → PDF + Thumbnail

    Steps:
    1. Upload image/screenshot of FSE window
    2. PaddleOCR extracts text
    3. ocr_to_schema structures data (no API key needed)
    4. fill_template fills the Word template → PDF
    5. create_thumbnail generates JPG thumbnail
    6. Returns PDF + thumbnail paths
    """
    try:
        if not ocr_engine:
            raise HTTPException(status_code=500, detail="OCR engine not initialized")

        import uuid
        content = await file.read()
        file_ext = Path(file.filename).suffix.lower() if file.filename else '.jpg'
        unique_id = str(uuid.uuid4())[:8]
        temp_path = os.path.join(temp_dir, f"upload_{unique_id}{file_ext}")

        with open(temp_path, 'wb') as f:
            f.write(content)

        image_path = None
        try:
            # Step 1: OCR
            logger.info(f"Running OCR on {file.filename}")
            ocr_text_lines, ocr_text, ocr_results_with_conf, image_path = run_ocr_on_file(
                temp_path, file_ext, unique_id
            )
            logger.info(f"OCR extracted {len(ocr_text_lines)} lines")

            # Step 2: Structure data (no API)
            extraction_data = extract_schema_from_ocr(ocr_results_with_conf, ocr_text)

            # Step 3: Fill template → PDF
            center_info = get_center_info()
            backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            sys.path.insert(0, backend_dir)
            from fill_template import fill_and_convert_to_pdf

            fse_number = extraction_data.get("fse_number", unique_id)
            os.makedirs(edm_base_path, exist_ok=True)
            pdf_output = os.path.join(edm_base_path, f"Prescription_{finess}_FSE_{fse_number}.pdf")

            def generate_pdf_sync():
                return fill_and_convert_to_pdf(
                    extraction_data=extraction_data,
                    output_pdf_path=pdf_output,
                    center_info=center_info,
                    finess=finess,
                    city=city,
                )

            pdf_path = await asyncio.get_event_loop().run_in_executor(None, generate_pdf_sync)
            logger.info(f"✅ PDF generated: {pdf_path}")

            # Step 4: Create thumbnail
            thumbnail_path = None
            try:
                from prescription_generator import create_thumbnail
                thumbnail_dir = os.path.join(edm_base_path, "thumbnails")
                os.makedirs(thumbnail_dir, exist_ok=True)
                thumbnail_filename = f"Prescription_{finess}_FSE_{fse_number}.jpg"
                thumbnail_path = os.path.join(thumbnail_dir, thumbnail_filename)

                def create_thumb_sync():
                    return create_thumbnail(pdf_path, thumbnail_path)

                await asyncio.get_event_loop().run_in_executor(None, create_thumb_sync)
                logger.info(f"✅ Thumbnail created: {thumbnail_path}")
            except Exception as e:
                logger.warning(f"⚠️ Thumbnail creation failed (non-blocking): {e}")

            return PrescriptionResponse(
                success=True,
                message="Prescription générée avec succès",
                pdf_path=pdf_path,
                thumbnail_path=thumbnail_path,
                edm_path=edm_base_path
            )

        finally:
            try:
                os.unlink(temp_path)
                if image_path and os.path.exists(image_path):
                    os.unlink(image_path)
            except Exception:
                pass

    except Exception as e:
        logger.error(f"parse-and-generate failed: {str(e)}")
        return PrescriptionResponse(
            success=False,
            message=f"Erreur: {str(e)}",
            error=str(e)
        )


@app.post("/generate-prescription", response_model=PrescriptionResponse)
async def generate_prescription_endpoint(request: PrescriptionRequest):
    """Generate prescription PDF from structured FSE data"""
    try:
        from prescription_generator import generate_prescription

        def generate_sync():
            return generate_prescription(
                patient_info=request.patient,
                prescriber_initials=request.prescriber_initials,
                amy_code=request.amy_code,
                finess=request.finess,
                fse_number=request.fse_number,
                edm_base_path=request.edm_base_path,
                template_path=request.template_path
            )

        result = await asyncio.get_event_loop().run_in_executor(None, generate_sync)

        if result.get('success'):
            return PrescriptionResponse(
                success=True,
                message="Prescription générée avec succès",
                pdf_path=result.get('pdf_path'),
                thumbnail_path=result.get('thumbnail_path'),
                edm_path=result.get('edm_path')
            )
        else:
            return PrescriptionResponse(
                success=False,
                message="Échec de la génération de la prescription",
                error=result.get('error', 'Unknown error')
            )

    except Exception as e:
        logger.error(f"Prescription generation failed: {str(e)}")
        return PrescriptionResponse(
            success=False,
            message=f"Erreur: {str(e)}",
            error=str(e)
        )


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=7861)
