#!/usr/bin/env python3
"""
FSE OCR API - FastAPI Backend with PaddleOCR
Simplified version for window capture screenshot processing
"""
import zipfile
import shutil
import os
import sys
import platform
import tempfile
import uuid
from typing import Optional
from pathlib import Path
import asyncio
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from datetime import datetime

# ── Resolve paths relative to this file (works in dev and bundled installs) ──
BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BACKEND_DIR.parent

# Load .env from backend root (next to api/), fallback to project root
_env_path = BACKEND_DIR / ".env"
if not _env_path.exists():
    _env_path = PROJECT_ROOT / ".env"
load_dotenv(str(_env_path))

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from tempfile import gettempdir
from loguru import logger
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# ── Logging configuration ────────────────────────────────────────────────────
# Determine log directory: NEUROX_LOG_DIR env var → {project_root}/logs
LOG_DIR = Path(os.getenv("NEUROX_LOG_DIR", str(PROJECT_ROOT / "logs")))
LOG_DIR.mkdir(parents=True, exist_ok=True)

# Remove default stderr handler and re-add with consistent format
logger.remove()
logger.add(
    sys.stderr,
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level:<8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
)
logger.add(
    str(LOG_DIR / "backend_{time:YYYY-MM-DD}.log"),
    rotation="10 MB",
    retention="30 days",
    compression="zip",
    level=os.getenv("LOG_LEVEL", "DEBUG"),
    format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level:<8} | {name}:{function}:{line} - {message}",
    encoding="utf-8",
)

logger.info(f"Backend log directory: {LOG_DIR}")
logger.info(f"Environment file: {_env_path} (exists={_env_path.exists()})")

sys.path.append(str(BACKEND_DIR))
from database import init_db, close_db

# ── Center config from .env ──────────────────────────────────────────────────
def get_center_info() -> dict:
    return {
        "name":    os.getenv("CENTER_NAME",    "CDS OPHTALMOLOGIE NANTERRE LA BOULE"),
        "address": os.getenv("CENTER_ADDRESS", "123 Avenue de la République, 92000 Nanterre"),
        "tel":     os.getenv("CENTER_TEL",     "01 47 00 00 00"),
        "email":   os.getenv("CENTER_EMAIL",   "contact@cds-nanterre.fr"),
    }

CENTER_FINESS  = os.getenv("CENTER_FINESS",  "920036563")
CENTER_CITY    = os.getenv("CENTER_CITY",    "Nanterre")
EDM_BASE_PATH  = os.getenv("EDM_BASE_PATH",  "C:/temp/fse_ocr")
GALAXIE_EDM    = os.getenv("GALAXIE_EDM",    "D:/Stimut/Documents_Patients")


# ── EDM path helpers ─────────────────────────────────────────────────────────

def ipp_to_edm_path(ipp: str) -> str:
    """
    Convert IPP number to Galaxie EDM directory path.
    Read digits from right to left in pairs:
    15035  → 00/00/00/15/03/5
    145897 → 00/00/01/45/89/7
    """
    s = str(ipp).strip()
    unit = s[-1]          # last digit = unit folder
    rest = s[:-1]         # remaining digits

    pairs = []
    while rest:
        pairs.append(rest[-2:].zfill(2))
        rest = rest[:-2]

    # Always 5 pairs + unit = 6 folders total
    while len(pairs) < 5:
        pairs.append("00")

    pairs.reverse()
    return os.path.join(*pairs, unit)


def get_edm_dir(ipp: str, base_path: str) -> str:
    """Full EDM directory path for a patient IPP."""
    return os.path.join(base_path, ipp_to_edm_path(ipp))


def update_info_pdf(edm_dir: str, pdf_filename: str, jpg_filename: str):
    """
    Append a line to infoPdf file in the EDM directory.
    Format: pdf_filename|jpg_filename|timestamp
    """
    info_pdf_path = os.path.join(edm_dir, "infoPdf")
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"{pdf_filename}|{jpg_filename}|{timestamp}\n"
    try:
        with open(info_pdf_path, "a", encoding="utf-8") as f:
            f.write(line)
        logger.info(f"✅ infoPdf updated: {info_pdf_path}")
    except Exception as e:
        logger.warning(f"⚠️ Could not update infoPdf: {e}")


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


def _log_cpu_capabilities() -> dict:
    """Log CPU instruction-set support (AVX, AVX2, SSE4.2 etc.).
    PaddlePaddle's default Windows wheel is compiled with AVX; on CPUs or
    VMs that do not expose AVX the native `libpaddle` DLL init routine fails.
    """
    info = {"avx": None, "avx2": None, "sse4_2": None, "source": None, "processor": platform.processor()}
    # Try cpuinfo (best signal)
    try:
        import cpuinfo  # type: ignore
        data = cpuinfo.get_cpu_info()
        flags = set(data.get("flags", []))
        info.update({
            "avx": "avx" in flags,
            "avx2": "avx2" in flags,
            "sse4_2": "sse4_2" in flags,
            "source": "py-cpuinfo",
            "brand": data.get("brand_raw"),
        })
    except Exception:
        # Fallback: Windows PowerShell WMI query for CPU flags is unreliable;
        # use wmic for at least the CPU name and let paddle report AVX itself.
        if sys.platform == "win32":
            try:
                import subprocess
                out = subprocess.check_output(
                    ["wmic", "cpu", "get", "Name,Caption,Description", "/format:list"],
                    stderr=subprocess.DEVNULL, text=True, timeout=5,
                )
                info["source"] = "wmic"
                info["wmic"] = out.strip().replace("\r", "")
            except Exception as ex:
                info["source"] = f"unavailable ({ex})"
    logger.info(f"CPU capabilities: {info}")
    if info["avx"] is False:
        logger.warning(
            "⚠️ CPU does NOT expose AVX. PaddlePaddle's default AVX build will fail to load."
        )
    return info


def _register_paddle_dll_dirs() -> None:
    """On Windows + Python 3.8+, PATH is not used for loading C extension
    dependencies. Paddle's own __init__ is supposed to register its libs
    directory, but in embedded/packaged layouts it sometimes fails. We
    pre-register every known candidate directory so libpaddle can import.
    """
    if sys.platform != "win32" or not hasattr(os, "add_dll_directory"):
        return
    import site as _site
    candidates = []
    try:
        candidates.extend(_site.getsitepackages())
    except Exception:
        pass
    candidates.append(str(Path(sys.executable).parent / "Lib" / "site-packages"))
    seen = set()
    for sp in candidates:
        libs_dir = Path(sp) / "paddle" / "libs"
        if libs_dir.exists() and str(libs_dir) not in seen:
            try:
                os.add_dll_directory(str(libs_dir))
                seen.add(str(libs_dir))
                logger.info(f"Registered paddle DLL dir: {libs_dir}")
            except OSError as e:
                logger.warning(f"Could not register paddle DLL dir {libs_dir}: {e}")


def initialize_ocr():
    global ocr_engine
    if ocr_engine is None:
        try:
            cpu_info = _log_cpu_capabilities()
            # PaddlePaddle's default wheel requires AVX. On VMs / older CPUs
            # without AVX, libpaddle.pyd fails to initialize and the whole
            # paddle import blows up with a confusing NameError. Detect this
            # early and bail out cleanly with a clear message.
            if cpu_info.get("avx") is False:
                raise RuntimeError(
                    "CPU does not support AVX instructions; the bundled "
                    "PaddlePaddle build cannot run on this machine. "
                    "OCR will be disabled. Fix: ship a paddlepaddle-noavx "
                    "wheel or run on a CPU/VM that exposes AVX."
                )
            _register_paddle_dll_dirs()
            from paddleocr import PaddleOCR
            ocr_engine = PaddleOCR(
                use_textline_orientation=True,
                use_doc_orientation_classify=False,
                use_doc_unwarping=False,
                text_detection_model_name='PP-OCRv5_mobile_det',
                text_recognition_model_name='PP-OCRv5_mobile_rec',
            )
            logger.info("✅ PaddleOCR initialized successfully")
        except Exception as e:
            import traceback
            logger.error(f"Failed to initialize PaddleOCR: {e}")
            logger.error(f"Full traceback:\n{traceback.format_exc()}")
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
    Full pipeline: Image → OCR → JSON → fill_template → PDF + Thumbnail + infoPdf
    """
    try:
        if not ocr_engine:
            raise HTTPException(status_code=500, detail="OCR engine not initialized")

        # Validate file type
        allowed_extensions = {'.pdf', '.jpg', '.jpeg', '.png'}
        file_ext = Path(file.filename).suffix.lower() if file.filename else ''
        if file_ext not in allowed_extensions:
            raise HTTPException(status_code=400, detail=f"Unsupported file type: {file_ext}. Use /process-zip for ZIP files.")

        content = await file.read()
        unique_id = str(uuid.uuid4())[:8]
        temp_path = os.path.join(temp_dir, f"upload_{unique_id}{file_ext}")

        with open(temp_path, 'wb') as f:
            f.write(content)

        image_path = None
        try:
            logger.info(f"Running OCR on {file.filename}")
            ocr_text_lines, ocr_text, ocr_results_with_conf, image_path = run_ocr_on_file(
                temp_path, file_ext, unique_id
            )
            logger.info(f"OCR extracted {len(ocr_text_lines)} lines")

            extraction_data = extract_schema_from_ocr(ocr_results_with_conf, ocr_text)

            center_info = get_center_info()
            backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            sys.path.insert(0, backend_dir)
            from fill_template import fill_and_convert_to_pdf
            current_dir = os.path.dirname(os.path.abspath(__file__))
            project_root = os.path.dirname(current_dir)
            template_path = os.path.join(project_root, "templates", "prescription", "Ordonnance_Template_vierge.docx")

            logger.info(f"Looking for template at: {template_path}")
            if not os.path.exists(template_path):
                logger.error(f"Template not found at {template_path}")
                raise HTTPException(status_code=500, detail=f"Template not found: {template_path}")

            fse_number = str(extraction_data.get("fse_number") or unique_id)
            ipp = str(extraction_data.get("patient", {}).get("ipp") or
                      extraction_data.get("ipp") or fse_number)

            edm_dir = get_edm_dir(ipp, edm_base_path)
            os.makedirs(edm_dir, exist_ok=True)
            os.makedirs(os.path.join(edm_dir, "thumbnails"), exist_ok=True)
            logger.info(f"EDM directory: {edm_dir}")

            pdf_filename = f"Ordonnance_{finess}_{fse_number}.pdf"
            jpg_filename = f"Ordonnance_{finess}_{fse_number}.jpg"
            pdf_output = os.path.join(edm_dir, pdf_filename)
            thumbnail_path = os.path.join(edm_dir, "thumbnails", jpg_filename)

            def generate_pdf_sync():
                return fill_and_convert_to_pdf(
                    extraction_data=extraction_data,
                    output_pdf_path=pdf_output,
                    center_info=center_info,
                    finess=finess,
                    city=city,
                    template_path=template_path,
                )

            pdf_path = await asyncio.get_event_loop().run_in_executor(None, generate_pdf_sync)
            logger.info(f"✅ PDF generated: {pdf_path}")

            try:
                from prescription_generator import create_thumbnail
                def create_thumb_sync():
                    return create_thumbnail(pdf_path, thumbnail_path)
                await asyncio.get_event_loop().run_in_executor(None, create_thumb_sync)
                logger.info(f"✅ Thumbnail created: {thumbnail_path}")
            except Exception as e:
                logger.warning(f"⚠️ Thumbnail creation failed (non-blocking): {e}")
                thumbnail_path = None

            update_info_pdf(edm_dir, pdf_filename, jpg_filename)

            return PrescriptionResponse(
                success=True,
                message="Prescription générée avec succès",
                pdf_path=pdf_path,
                thumbnail_path=thumbnail_path,
                edm_path=edm_dir
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


# ─────────────────────────────────────────────────────────────────────────────
# ZIP PROCESSING ENDPOINT
# ─────────────────────────────────────────────────────────────────────────────
@app.post("/process-zip", response_model=PrescriptionResponse)
async def process_zip(
    file: UploadFile = File(...),
    finess: str = CENTER_FINESS,
    city: str = CENTER_CITY,
    edm_base_path: str = EDM_BASE_PATH,
):
    """
    Process a ZIP file containing multiple frames (images/PDFs).
    Extracts all images, runs OCR on each, combines results, then generates a single prescription PDF.
    """
    logger.info("=== Entered /process-zip ===")
    try:
        if not ocr_engine:
            raise HTTPException(status_code=500, detail="OCR engine not initialized")

        # Create a temporary directory for extraction
        with tempfile.TemporaryDirectory() as tmpdir:
            zip_path = os.path.join(tmpdir, "upload.zip")
            with open(zip_path, "wb") as f:
                content = await file.read()
                f.write(content)

            # Extract ZIP
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(tmpdir)

            # Gather all image files (recursively)
            image_extensions = {'.jpg', '.jpeg', '.png', '.pdf'}
            image_paths = []
            for root, dirs, files in os.walk(tmpdir):
                for fname in files:
                    ext = os.path.splitext(fname)[1].lower()
                    if ext in image_extensions:
                        image_paths.append(os.path.join(root, fname))

            if not image_paths:
                raise HTTPException(status_code=400, detail="No images or PDFs found in ZIP")

            logger.info(f"Found {len(image_paths)} image/PDF files in ZIP")

            # Combine OCR results from all frames
            all_ocr_results = []
            for idx, img_path in enumerate(image_paths):
                unique_id = str(uuid.uuid4())[:8]
                file_ext = os.path.splitext(img_path)[1].lower()
                logger.info(f"Processing frame {idx+1}/{len(image_paths)}: {os.path.basename(img_path)}")
                _, _, ocr_results, _ = run_ocr_on_file(img_path, file_ext, unique_id)
                if ocr_results:
                    all_ocr_results.extend(ocr_results)
                    logger.info(f"  -> {len(ocr_results)} OCR lines extracted")
                else:
                    logger.warning(f"  -> No OCR results from {img_path}")

            if not all_ocr_results:
                raise HTTPException(status_code=400, detail="No OCR text detected in any frame")

            extraction_data = extract_schema_from_ocr(all_ocr_results, "")
            logger.info(f"Extraction data keys: {list(extraction_data.keys())}")

            fse_number = str(extraction_data.get("fse_number") or str(uuid.uuid4())[:8])
            ipp = str(extraction_data.get("patient", {}).get("ipp") or
                      extraction_data.get("ipp") or fse_number)

            center_info = get_center_info()
            from fill_template import fill_and_convert_to_pdf
            current_dir = os.path.dirname(os.path.abspath(__file__))
            project_root = os.path.dirname(current_dir)
            template_path = os.path.join(project_root, "templates", "prescription", "Ordonnance_Template_vierge.docx")
            if not os.path.exists(template_path):
                raise HTTPException(status_code=500, detail=f"Template not found: {template_path}")

            edm_dir = get_edm_dir(ipp, edm_base_path)
            os.makedirs(edm_dir, exist_ok=True)
            os.makedirs(os.path.join(edm_dir, "thumbnails"), exist_ok=True)

            pdf_filename = f"Ordonnance_{finess}_{fse_number}.pdf"
            jpg_filename = f"Ordonnance_{finess}_{fse_number}.jpg"
            pdf_output = os.path.join(edm_dir, pdf_filename)
            thumbnail_path = os.path.join(edm_dir, "thumbnails", jpg_filename)

            def generate_pdf_sync():
                return fill_and_convert_to_pdf(
                    extraction_data=extraction_data,
                    output_pdf_path=pdf_output,
                    center_info=center_info,
                    finess=finess,
                    city=city,
                    template_path=template_path,
                )
            pdf_path = await asyncio.get_event_loop().run_in_executor(None, generate_pdf_sync)
            logger.info(f"✅ PDF generated from ZIP: {pdf_path}")

            try:
                from prescription_generator import create_thumbnail
                await asyncio.get_event_loop().run_in_executor(None, create_thumbnail, pdf_path, thumbnail_path)
                logger.info(f"✅ Thumbnail created: {thumbnail_path}")
            except Exception as e:
                logger.warning(f"⚠️ Thumbnail creation failed: {e}")
                thumbnail_path = None

            update_info_pdf(edm_dir, pdf_filename, jpg_filename)

            return PrescriptionResponse(
                success=True,
                message=f"Prescription générée avec succès à partir de {len(image_paths)} frames",
                pdf_path=pdf_path,
                thumbnail_path=thumbnail_path,
                edm_path=edm_dir
            )

    except Exception as e:
        logger.error(f"process-zip failed: {str(e)}")
        return PrescriptionResponse(
            success=False,
            message=f"Erreur: {str(e)}",
            error=str(e)
        )


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=7861)