"""
Database-related API routes
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from database import get_db
from api import crud, schemas

router = APIRouter(prefix="/api", tags=["database"])

# Document endpoints
@router.post("/documents", response_model=schemas.DocumentResponse, status_code=201)
async def create_document(
    document: schemas.DocumentCreate,
    db: AsyncSession = Depends(get_db)
):
    """Create a new document record"""
    db_doc = await crud.create_document(db, document)
    return schemas.DocumentResponse(
        id=db_doc.id,
        filename=db_doc.filename,
        file_type=db_doc.file_type,
        task_type=db_doc.task_type,
        content=db_doc.content,
        metadata=db_doc.doc_metadata,
        output_path=db_doc.output_path,
        status=db_doc.status,
        error_message=db_doc.error_message,
        created_at=db_doc.created_at,
        updated_at=db_doc.updated_at,
    )

@router.get("/documents", response_model=List[schemas.DocumentResponse])
async def get_documents(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    status: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db)
):
    """Get list of documents"""
    documents = await crud.get_documents(db, skip=skip, limit=limit, status=status)
    return documents

@router.get("/documents/{document_id}", response_model=schemas.DocumentResponse)
async def get_document(
    document_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Get a specific document"""
    document = await crud.get_document(db, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    return document

@router.patch("/documents/{document_id}", response_model=schemas.DocumentResponse)
async def update_document(
    document_id: int,
    document_update: schemas.DocumentUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Update a document"""
    document = await crud.update_document(db, document_id, document_update)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    return document

@router.delete("/documents/{document_id}", response_model=schemas.MessageResponse)
async def delete_document(
    document_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Delete a document"""
    deleted = await crud.delete_document(db, document_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Document not found")
    return schemas.MessageResponse(message="Document deleted successfully")

# Processing Job endpoints
@router.post("/jobs", response_model=schemas.ProcessingJobResponse, status_code=201)
async def create_job(
    job: schemas.ProcessingJobCreate,
    db: AsyncSession = Depends(get_db)
):
    """Create a new processing job"""
    return await crud.create_processing_job(db, job)

@router.get("/jobs", response_model=List[schemas.ProcessingJobResponse])
async def get_jobs(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    status: Optional[str] = Query(None),
    user_id: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db)
):
    """Get list of processing jobs"""
    jobs = await crud.get_processing_jobs(
        db, skip=skip, limit=limit, status=status, user_id=user_id
    )
    return jobs

@router.get("/jobs/{job_id}", response_model=schemas.ProcessingJobResponse)
async def get_job(
    job_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Get a specific processing job"""
    job = await crud.get_processing_job(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job

@router.patch("/jobs/{job_id}", response_model=schemas.ProcessingJobResponse)
async def update_job(
    job_id: str,
    job_update: schemas.ProcessingJobUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Update a processing job"""
    job = await crud.update_processing_job(db, job_id, job_update)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job

@router.delete("/jobs/{job_id}", response_model=schemas.MessageResponse)
async def delete_job(
    job_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Delete a processing job"""
    deleted = await crud.delete_processing_job(db, job_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Job not found")
    return schemas.MessageResponse(message="Job deleted successfully")

# Medical List endpoints
@router.post("/medical-lists", response_model=schemas.MedicalListResponse, status_code=201)
async def create_medical_list(
    medical_list: schemas.MedicalListCreate,
    db: AsyncSession = Depends(get_db)
):
    """Create a new medical list item"""
    # Check if code already exists
    existing = await crud.get_medical_list_by_code(db, medical_list.code)
    if existing:
        raise HTTPException(status_code=400, detail=f"Medical list with code {medical_list.code} already exists")
    return await crud.create_medical_list(db, medical_list)

@router.post("/medical-lists/bulk", response_model=List[schemas.MedicalListResponse], status_code=201)
async def bulk_create_medical_lists(
    medical_lists: List[schemas.MedicalListCreate],
    db: AsyncSession = Depends(get_db)
):
    """Bulk create medical list items"""
    return await crud.bulk_create_medical_lists(db, medical_lists)

@router.get("/medical-lists", response_model=List[schemas.MedicalListResponse])
async def get_medical_lists(
    skip: int = Query(0, ge=0),
    limit: int = Query(1000, ge=1, le=10000),
    category: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    db: AsyncSession = Depends(get_db)
):
    """Get list of medical list items"""
    medical_lists = await crud.get_medical_lists(
        db, skip=skip, limit=limit, category=category, is_active=is_active
    )
    return medical_lists

@router.get("/medical-lists/search", response_model=List[schemas.MedicalListResponse])
async def search_medical_lists(
    codes: str = Query(..., description="Comma-separated list of AMY codes (e.g., 'AMY 7,AMY 8,AMY 15')"),
    db: AsyncSession = Depends(get_db)
):
    """Search medical list items by codes"""
    code_list = [code.strip() for code in codes.split(",") if code.strip()]
    if not code_list:
        raise HTTPException(status_code=400, detail="At least one code is required")
    medical_lists = await crud.search_medical_lists_by_codes(db, code_list)
    return medical_lists

@router.get("/medical-lists/{medical_list_id}", response_model=schemas.MedicalListResponse)
async def get_medical_list(
    medical_list_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Get a specific medical list item"""
    medical_list = await crud.get_medical_list(db, medical_list_id)
    if not medical_list:
        raise HTTPException(status_code=404, detail="Medical list not found")
    return medical_list

@router.get("/medical-lists/code/{code}", response_model=schemas.MedicalListResponse)
async def get_medical_list_by_code(
    code: str,
    db: AsyncSession = Depends(get_db)
):
    """Get a medical list item by code"""
    medical_list = await crud.get_medical_list_by_code(db, code)
    if not medical_list:
        raise HTTPException(status_code=404, detail=f"Medical list with code {code} not found")
    return medical_list

@router.patch("/medical-lists/{medical_list_id}", response_model=schemas.MedicalListResponse)
async def update_medical_list(
    medical_list_id: int,
    medical_list_update: schemas.MedicalListUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Update a medical list item"""
    medical_list = await crud.update_medical_list(db, medical_list_id, medical_list_update)
    if not medical_list:
        raise HTTPException(status_code=404, detail="Medical list not found")
    return medical_list

@router.delete("/medical-lists/{medical_list_id}", response_model=schemas.MessageResponse)
async def delete_medical_list(
    medical_list_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Delete a medical list item"""
    deleted = await crud.delete_medical_list(db, medical_list_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Medical list not found")
    return schemas.MessageResponse(message="Medical list deleted successfully")

# Health check endpoint
@router.get("/health", response_model=schemas.MessageResponse)
async def health_check(db: AsyncSession = Depends(get_db)):
    """Check database connection health"""
    try:
        # Simple query to check connection
        await db.execute("SELECT 1")
        return schemas.MessageResponse(
            message="Database connection healthy",
            success=True
        )
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"Database connection failed: {str(e)}"
        )


