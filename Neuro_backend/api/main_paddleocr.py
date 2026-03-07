#!/usr/bin/env python3
"""
FSE OCR API - FastAPI Backend with PaddleOCR
Simplified version for window capture screenshot processing
"""

import os
import io
import tempfile
from typing import Optional, List
from pathlib import Path
import asyncio
from contextlib import asynccontextmanager
from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from tempfile import gettempdir
from loguru import logger
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# Import database utilities
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database import init_db, close_db

# Response models
class ParseResponse(BaseModel):
    success: bool
    message: str
    content: Optional[str] = None
    extract: Optional[dict] = None

class PrescriptionRequest(BaseModel):
    patient: dict  # {lastName, firstName, ssn, ipp}
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

# Global OCR instance
ocr_engine = None

def initialize_ocr():
    """Initialize PaddleOCR engine"""
    global ocr_engine
    if ocr_engine is None:
        try:
            from paddleocr import PaddleOCR
            # Initialize PaddleOCR with English and French support
            ocr_engine = PaddleOCR(
                use_angle_cls=True,  # Enable text angle detection
                lang='fr',  # French language
                use_gpu=False,  # Set to True if GPU available
                show_log=False
            )
            logger.info("✅ PaddleOCR initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize PaddleOCR: {e}")
            raise
    return ocr_engine

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event handler"""
    # Startup
    try:
        await init_db()
        logger.info("✅ Database initialized successfully")
    except Exception as e:
        logger.warning(f"⚠️  Database initialization failed (continuing without DB): {e}")
    
    try:
        initialize_ocr()
    except Exception as e:
        logger.warning(f"⚠️ Failed to initialize OCR: {e}")
        logger.warning("⚠️ OCR features will be disabled")
    
    yield
    
    # Shutdown
    try:
        await close_db()
    except Exception as e:
        logger.warning(f"⚠️  Error closing database: {e}")
    
    logger.info("🔄 Application shutdown complete")

app = FastAPI(
    title="FSE OCR API",
    description="OCR API for French medical prescription processing using PaddleOCR",
    version="2.0.0",
    lifespan=lifespan
)

# CORS configuration
cors_origins = os.getenv("CORS_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins if cors_origins != ["*"] else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include database routes
from api.routes import router as db_router
app.include_router(db_router)

# Include authentication routes
from api.auth import router as auth_router
app.include_router(auth_router)

# Temp directory for static files
temp_dir = os.getenv("TMPDIR", gettempdir())
logger.info(f"Using temporary directory: {temp_dir}")
os.makedirs(temp_dir, exist_ok=True)
app.mount("/static", StaticFiles(directory=temp_dir), name="static")

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "FSE OCR API is running",
        "version": "2.0.0",
        "ocr_engine": "PaddleOCR"
    }

@app.post("/parse", response_model=ParseResponse)
async def parse_document(file: UploadFile = File(...)):
    """
    Parse document/screenshot using PaddleOCR
    
    Workflow:
    1. Receive image/PDF from frontend (screenshot of FSE window)
    2. Run PaddleOCR to extract text
    3. Use OpenAI API to structure the extracted data
    4. Return structured JSON
    """
    try:
        if not ocr_engine:
            raise HTTPException(status_code=500, detail="OCR engine not initialized")
        
        # Validate file type
        allowed_extensions = {'.pdf', '.jpg', '.jpeg', '.png'}
        file_ext = Path(file.filename).suffix.lower() if file.filename else ''
        
        if file_ext not in allowed_extensions:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type: {file_ext}. Allowed: {', '.join(allowed_extensions)}"
            )
        
        # Read uploaded file
        content = await file.read()
        
        # Save temporarily
        import uuid
        unique_id = str(uuid.uuid4())[:8]
        temp_path = os.path.join(temp_dir, f"upload_{unique_id}{file_ext}")
        
        with open(temp_path, 'wb') as f:
            f.write(content)
        
        try:
            # Step 1: Run PaddleOCR
            logger.info(f"Running PaddleOCR on {file.filename}")
            
            # If PDF, convert to image first
            if file_ext == '.pdf':
                from pdf2image import convert_from_path
                images = convert_from_path(temp_path, dpi=300)
                # Process first page only for now
                image_path = os.path.join(temp_dir, f"pdf_page_{unique_id}.jpg")
                images[0].save(image_path, 'JPEG')
                ocr_input = image_path
            else:
                ocr_input = temp_path
            
            # Run OCR
            result = ocr_engine.ocr(ocr_input, cls=True)
            
            # Extract text from OCR result
            ocr_text_lines = []
            if result and result[0]:
                for line in result[0]:
                    if line and len(line) >= 2:
                        text = line[1][0]  # Extract text from structure
                        confidence = line[1][1]  # Extract confidence
                        if confidence > 0.5:  # Filter low confidence
                            ocr_text_lines.append(text)
            
            ocr_text = "\n".join(ocr_text_lines)
            logger.info(f"OCR extracted {len(ocr_text_lines)} lines of text")
            
            # Step 2: Structure the data using OpenAI API (from openai_extraction.py)
            extract = None
            try:
                from openai_extraction import call_openai_extract
                extract = call_openai_extract(ocr_text)
                logger.info("✅ Structured extraction completed")
            except Exception as e:
                logger.warning(f"⚠️ OpenAI extraction failed: {e}")
                # Return raw OCR text even if extraction fails
                extract = {"ocr_raw_text": ocr_text}
            
            return ParseResponse(
                success=True,
                message="OCR processing completed successfully",
                content=ocr_text,
                extract=extract
            )
            
        finally:
            # Cleanup temp files
            try:
                os.unlink(temp_path)
                if file_ext == '.pdf' and 'image_path' in locals():
                    os.unlink(image_path)
            except Exception as e:
                logger.warning(f"Failed to cleanup temp files: {e}")
        
    except Exception as e:
        logger.error(f"Parsing failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Parsing failed: {str(e)}")

@app.post("/generate-prescription", response_model=PrescriptionResponse)
async def generate_prescription_endpoint(request: PrescriptionRequest):
    """
    Generate prescription PDF from FSE data.
    
    Steps:
    1. READ: Extract AMY code from request
    2. SEARCH: Search official AMY table
    3. GENERATE: Create PDF prescription with complete information
    4. STORE: Save to EDM system
    5. THUMBNAIL: Create thumbnail
    6. UPDATE: Update infoPdf file
    """
    try:
        from prescription_generator import generate_prescription
        
        # Run prescription generation in thread pool
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
