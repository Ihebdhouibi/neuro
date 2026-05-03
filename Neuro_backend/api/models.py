"""
Database models for the application
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, Float, JSON, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base


class Document(Base):
    """
    Model for storing parsed documents
    """
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String(255), nullable=False)
    file_type = Column(String(50), nullable=False)  # pdf, jpg, png, etc.
    task_type = Column(String(50), nullable=False)  # parse, text, table, formula, etc.
    content = Column(Text, nullable=True)  # Extracted content
    doc_metadata = Column(JSON, nullable=True)  # Additional metadata (renamed from 'metadata' to avoid SQLAlchemy conflict)
    output_path = Column(String(500), nullable=True)  # Path to output files
    status = Column(String(50), default="pending")  # pending, processing, completed, failed
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def to_dict(self):
        """Convert model to dictionary"""
        return {
            "id": self.id,
            "filename": self.filename,
            "file_type": self.file_type,
            "task_type": self.task_type,
            "content": self.content,
            "metadata": self.doc_metadata,  # Return as 'metadata' for API compatibility
            "output_path": self.output_path,
            "status": self.status,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class User(Base):
    """
    Model for user management
    """
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    full_name = Column(String(255), nullable=True)
    hashed_password = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    is_superuser = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def to_dict(self):
        """Convert model to dictionary (excluding password)"""
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "full_name": self.full_name,
            "is_active": self.is_active,
            "is_superuser": self.is_superuser,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class ProcessingJob(Base):
    """
    Model for tracking processing jobs
    """
    __tablename__ = "processing_jobs"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(String(100), unique=True, nullable=False, index=True)
    user_id = Column(Integer, nullable=True)  # Optional: link to user
    job_type = Column(String(50), nullable=False)  # parse, ocr, extract, etc.
    input_file = Column(String(500), nullable=False)
    output_files = Column(JSON, nullable=True)  # List of output file paths
    status = Column(String(50), default="pending")  # pending, processing, completed, failed
    progress = Column(Float, default=0.0)  # 0.0 to 100.0
    result_data = Column(JSON, nullable=True)  # Store result data
    error_message = Column(Text, nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def to_dict(self):
        """Convert model to dictionary"""
        return {
            "id": self.id,
            "job_id": self.job_id,
            "user_id": self.user_id,
            "job_type": self.job_type,
            "input_file": self.input_file,
            "output_files": self.output_files,
            "status": self.status,
            "progress": self.progress,
            "result_data": self.result_data,
            "error_message": self.error_message,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class MedicalList(Base):
    """
    Model for storing medical procedure lists (AMY codes)
    """
    __tablename__ = "medical_lists"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(50), unique=True, nullable=False, index=True)  # e.g., "AMY 7", "AMY 8,7"
    category = Column(String(100), nullable=True)  # e.g., "BILANS ORTHOPTIQUES", "RÉÉDUCATION"
    label = Column(Text, nullable=False)  # Full description
    price = Column(Float, nullable=False)  # Price in Euros
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def to_dict(self):
        """Convert model to dictionary"""
        return {
            "id": self.id,
            "code": self.code,
            "category": self.category,
            "label": self.label,
            "price": self.price,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class Center(Base):
    """Centre d'orthoptie / établissement"""
    __tablename__ = "centers"
    
    id = Column(Integer, primary_key=True, index=True)
    nom = Column(String, unique=True, index=True, nullable=False)
    finess = Column(String, unique=True, index=True, nullable=False)
    adresse = Column(String, nullable=False)
    ville = Column(String, nullable=False)
    code_postal = Column(String, nullable=False)
    telephone = Column(String, nullable=True)
    email = Column(String, nullable=True)
    tampon_path = Column(String, nullable=True)
    signature_path = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Practitioner(Base):
    """Praticien (prescripteur ou orthoptiste exécutant)"""
    __tablename__ = "practitioners"
    
    id = Column(Integer, primary_key=True, index=True)
    centre = Column(String, index=True, nullable=False)
    pcode = Column(String, unique=True, index=True, nullable=False)
    nom = Column(String, nullable=False)
    prenom = Column(String, nullable=False)
    rpps = Column(String, index=True, nullable=True)
    type = Column(String, default="prescripteur")
    tarif = Column(Float, default=10.0)
    code_conventionnel = Column(String, nullable=True)
    ik = Column(String, nullable=True)
    parcours = Column(String, nullable=True)
    histo_dent = Column(String, nullable=True)
    condition_exercice = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Template(Base):
    """Template d'ordonnance (PDF)"""
    __tablename__ = "templates"
    
    id = Column(Integer, primary_key=True, index=True)
    center_id = Column(Integer, ForeignKey("centers.id", ondelete="CASCADE"), nullable=False)
    nom = Column(String, nullable=False)
    type = Column(String, nullable=False)  # 'FSE', 'B2', 'manuelle'
    contenu_html = Column(Text, nullable=True)
    contenu_path = Column(String, nullable=True)
    is_default = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relations
    center = relationship("Center", backref="templates")


class Prescription(Base):
    """Duplicata des ordonnances générées"""
    __tablename__ = "prescriptions"
    
    id = Column(Integer, primary_key=True, index=True)
    ordonnance_id = Column(String, unique=True, index=True, nullable=False)
    fse_number = Column(String, index=True, nullable=True)
    ipp_number = Column(String, index=True, nullable=True)
    
    # Patient
    patient_nom = Column(String, nullable=False)
    patient_prenom = Column(String, nullable=False)
    patient_nir = Column(String, nullable=True)
    patient_ipp = Column(String, nullable=True)
    
    # Prescripteur
    prescripteur_pcode = Column(String, ForeignKey("practitioners.pcode"), nullable=True)
    prescripteur_nom = Column(String, nullable=True)
    prescripteur_prenom = Column(String, nullable=True)
    prescripteur_rpps = Column(String, nullable=True)
    
    # Acte
    acte_code = Column(String, ForeignKey("medical_lists.code"), nullable=True)
    acte_libelle = Column(String, nullable=True)
    acte_tarif = Column(Float, nullable=True)
    
    # Centre
    center_finess = Column(String, ForeignKey("centers.finess"), nullable=True)
    center_nom = Column(String, nullable=True)
    
    # Métadonnées
    date_soin = Column(DateTime, nullable=True)
    date_generation = Column(DateTime, default=datetime.utcnow)
    pdf_path = Column(String, nullable=True)
    thumbnail_path = Column(String, nullable=True)
    status = Column(String, default="generated")
    error_message = Column(Text, nullable=True)
    mode_generation = Column(String, nullable=True)  # 'auto_fse', 'auto_b2', 'manuel'
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relations
    prescripteur = relationship("Practitioner", backref="prescriptions", foreign_keys=[prescripteur_pcode])
    acte = relationship("MedicalList", backref="prescriptions", foreign_keys=[acte_code])
    center = relationship("Center", backref="prescriptions", foreign_keys=[center_finess])