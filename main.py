import os
import re
import json
import uuid
import datetime
from typing import List, Optional
from fastapi import FastAPI, Depends, HTTPException, status, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, Column, Integer, String, Text, ForeignKey, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker, Session, relationship

# Import the AI Extractor service
from services.ai_extractor import AIExtractorService

# ==========================================
# 1. Database Configuration
# ==========================================
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://deepblue_user:deepblue_pass@localhost:5432/deepblue_db")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Helper dependency to get the database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ==========================================
# 2. SQLAlchemy Database Models
# ==========================================
class Asset(Base):
    __tablename__ = "assets"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    condition = Column(String(100), default="Good")
    status = Column(String(50), default="Operational")  # Operational, Maintenance Required, Offline

    reports = relationship("MaintenanceReport", back_populates="asset", cascade="all, delete-orphan")


class InventoryItem(Base):
    __tablename__ = "inventory"

    id = Column(Integer, primary_key=True, index=True)
    part_name = Column(String(100), nullable=False)
    part_number = Column(String(50), unique=True, index=True, nullable=False)
    quantity = Column(Integer, default=0)
    location = Column(String(100), default="Main Warehouse")


class MaintenanceReport(Base):
    __tablename__ = "maintenance_reports"

    id = Column(Integer, primary_key=True, index=True)
    asset_id = Column(Integer, ForeignKey("assets.id", ondelete="CASCADE"), nullable=False)
    description = Column(Text, nullable=False)
    action_taken = Column(Text, nullable=True)
    urgency = Column(String(50), default="Medium")  # Low, Medium, High

    asset = relationship("Asset", back_populates="reports")


class ExtractionTask(Base):
    __tablename__ = "extraction_tasks"

    id = Column(String(50), primary_key=True, default=lambda: str(uuid.uuid4()))
    status = Column(String(50), default="pending")  # pending, processing, completed, failed
    field_notes = Column(Text, nullable=False)
    extracted_data = Column(Text, nullable=True)  # JSON serialized string
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)


# NOTE: Table creation is now managed by Alembic migrations.
# Base.metadata.create_all(bind=engine)


# ==========================================
# 3. Pydantic Schemas
# ==========================================
# Asset Schemas
class AssetBase(BaseModel):
    name: str = Field(..., example="Thruster A")
    condition: str = Field(default="Good", example="Slight Wear")
    status: str = Field(default="Operational", example="Operational")

class AssetCreate(AssetBase):
    pass

class AssetResponse(AssetBase):
    id: int

    class Config:
        from_attributes = True

# Inventory Schemas
class InventoryBase(BaseModel):
    part_name: str = Field(..., example="O-Ring")
    part_number: str = Field(..., example="OR-992-G")
    quantity: int = Field(default=0, example=5)
    location: str = Field(default="Main Warehouse", example="Shelf A-4")

class InventoryCreate(InventoryBase):
    pass

class InventoryResponse(InventoryBase):
    id: int

    class Config:
        from_attributes = True

# Maintenance Schemas
class MaintenanceBase(BaseModel):
    asset_id: int = Field(..., example=1)
    description: str = Field(..., example="Engine overheating during trial run.")
    action_taken: Optional[str] = Field(default=None, example="Cleaned radiator filter.")
    urgency: str = Field(default="Medium", example="High")

class MaintenanceCreate(MaintenanceBase):
    pass

class MaintenanceResponse(MaintenanceBase):
    id: int

    class Config:
        from_attributes = True

# GenAI Extraction Schemas
class ExtractRequest(BaseModel):
    field_notes: str = Field(
        ..., 
        example="Thruster A seal showing wear near shaft seal #TS-293. Urgently need 2 replacement seals. Schedule replacement immediately."
    )

class ExtractAcceptedResponse(BaseModel):
    task_id: str
    status: str

class TaskResponse(BaseModel):
    task_id: str
    status: str
    field_notes: str
    extracted_data: Optional[dict] = None


# ==========================================
# 4. FastAPI Setup
# ==========================================
app = FastAPI(
    title="DeepBlue Supply API",
    description="Containerized, AI-enhanced microservice for offshore/marine asset and predictive maintenance tracking.",
    version="1.0.0"
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def read_root():
    return {"message": "Welcome to the DeepBlue Supply API. Visit /docs for Swagger UI documentation."}


# ==========================================
# 5. Background Task Executor
# ==========================================
async def process_extraction_task(task_id: str, field_notes: str):
    db = SessionLocal()
    try:
        # 1. Update task to processing
        task = db.query(ExtractionTask).filter(ExtractionTask.id == task_id).first()
        if not task:
            return
        task.status = "processing"
        db.commit()

        # 2. Call AI Extractor Service
        extractor = AIExtractorService()
        result = await extractor.extract(field_notes)

        # 3. Resolve and Update Asset
        asset_name = result.asset_name or "Unknown Marine Asset"
        db_asset = db.query(Asset).filter(Asset.name.ilike(asset_name)).first()
        
        # Map urgency to asset status
        asset_status = "Operational"
        if result.urgency.lower() == "high":
            asset_status = "Offline"
        elif result.urgency.lower() == "medium":
            asset_status = "Maintenance Required"

        if not db_asset:
            db_asset = Asset(
                name=asset_name,
                condition=result.condition or "Unknown",
                status=asset_status
            )
            db.add(db_asset)
            db.commit()
            db.refresh(db_asset)
        else:
            db_asset.condition = result.condition or db_asset.condition
            db_asset.status = asset_status
            db.commit()

        # 4. Create Maintenance Report
        db_report = MaintenanceReport(
            asset_id=db_asset.id,
            description=field_notes,
            action_taken=result.recommended_action,
            urgency=result.urgency
        )
        db.add(db_report)

        # 5. Resolve and Upsert Parts in Inventory
        for part in result.parts_identified:
            db_part = db.query(InventoryItem).filter(InventoryItem.part_number.ilike(part.part_number)).first()
            if not db_part:
                db_part = InventoryItem(
                    part_name=part.part_name,
                    part_number=part.part_number.upper(),
                    quantity=part.quantity,
                    location="Main Warehouse"
                )
                db.add(db_part)
            else:
                db_part.quantity += part.quantity
        
        # 6. Complete task with data payload
        task.status = "completed"
        task.extracted_data = json.dumps(result.model_dump())
        db.commit()

    except Exception as e:
        db.rollback()
        # Find task and mark as failed
        task = db.query(ExtractionTask).filter(ExtractionTask.id == task_id).first()
        if task:
            task.status = "failed"
            task.extracted_data = json.dumps({"error": str(e)})
            db.commit()
    finally:
        db.close()


# ==========================================
# 6. API Endpoints
# ==========================================

# --- Assets ---
@app.get("/api/v1/assets", response_model=List[AssetResponse], tags=["Assets"])
def list_assets(db: Session = Depends(get_db)):
    return db.query(Asset).all()

@app.post("/api/v1/assets", response_model=AssetResponse, status_code=status.HTTP_201_CREATED, tags=["Assets"])
def create_asset(asset: AssetCreate, db: Session = Depends(get_db)):
    db_asset = Asset(**asset.model_dump())
    db.add(db_asset)
    db.commit()
    db.refresh(db_asset)
    return db_asset

@app.get("/api/v1/assets/{id}", response_model=AssetResponse, tags=["Assets"])
def get_asset(id: int, db: Session = Depends(get_db)):
    db_asset = db.query(Asset).filter(Asset.id == id).first()
    if not db_asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    return db_asset

@app.put("/api/v1/assets/{id}", response_model=AssetResponse, tags=["Assets"])
def update_asset(id: int, asset: AssetCreate, db: Session = Depends(get_db)):
    db_asset = db.query(Asset).filter(Asset.id == id).first()
    if not db_asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    
    for key, value in asset.model_dump().items():
        setattr(db_asset, key, value)
    
    db.commit()
    db.refresh(db_asset)
    return db_asset

@app.delete("/api/v1/assets/{id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Assets"])
def delete_asset(id: int, db: Session = Depends(get_db)):
    db_asset = db.query(Asset).filter(Asset.id == id).first()
    if not db_asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    db.delete(db_asset)
    db.commit()
    return

# --- Inventory ---
@app.get("/api/v1/inventory", response_model=List[InventoryResponse], tags=["Inventory"])
def list_inventory(db: Session = Depends(get_db)):
    return db.query(InventoryItem).all()

@app.post("/api/v1/inventory", response_model=InventoryResponse, status_code=status.HTTP_201_CREATED, tags=["Inventory"])
def create_inventory_item(item: InventoryCreate, db: Session = Depends(get_db)):
    existing = db.query(InventoryItem).filter(InventoryItem.part_number == item.part_number).first()
    if existing:
         raise HTTPException(status_code=400, detail="Part number already exists in inventory")
    db_item = InventoryItem(**item.model_dump())
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    return db_item

@app.get("/api/v1/inventory/{id}", response_model=InventoryResponse, tags=["Inventory"])
def get_inventory_item(id: int, db: Session = Depends(get_db)):
    db_item = db.query(InventoryItem).filter(InventoryItem.id == id).first()
    if not db_item:
        raise HTTPException(status_code=404, detail="Inventory item not found")
    return db_item

@app.put("/api/v1/inventory/{id}", response_model=InventoryResponse, tags=["Inventory"])
def update_inventory_item(id: int, item: InventoryCreate, db: Session = Depends(get_db)):
    db_item = db.query(InventoryItem).filter(InventoryItem.id == id).first()
    if not db_item:
        raise HTTPException(status_code=404, detail="Inventory item not found")
    
    for key, value in item.model_dump().items():
        setattr(db_item, key, value)
    
    db.commit()
    db.refresh(db_item)
    return db_item

# --- Maintenance Reports ---
@app.get("/api/v1/maintenance", response_model=List[MaintenanceResponse], tags=["Maintenance Reports"])
def list_maintenance_reports(db: Session = Depends(get_db)):
    return db.query(MaintenanceReport).all()

@app.post("/api/v1/maintenance", response_model=MaintenanceResponse, status_code=status.HTTP_201_CREATED, tags=["Maintenance Reports"])
def create_maintenance_report(report: MaintenanceCreate, db: Session = Depends(get_db)):
    asset = db.query(Asset).filter(Asset.id == report.asset_id).first()
    if not asset:
        raise HTTPException(status_code=404, detail="Referenced asset id does not exist")
    db_report = MaintenanceReport(**report.model_dump())
    db.add(db_report)
    db.commit()
    db.refresh(db_report)
    return db_report

@app.get("/api/v1/maintenance/{id}", response_model=MaintenanceResponse, tags=["Maintenance Reports"])
def get_maintenance_report(id: int, db: Session = Depends(get_db)):
    db_report = db.query(MaintenanceReport).filter(MaintenanceReport.id == id).first()
    if not db_report:
        raise HTTPException(status_code=404, detail="Maintenance report not found")
    return db_report

# --- GenAI Extraction Endpoints ---
@app.post("/api/v1/extract", response_model=ExtractAcceptedResponse, status_code=status.HTTP_202_ACCEPTED, tags=["GenAI Extractor"])
def extract_context_async(request: ExtractRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    task_id = str(uuid.uuid4())
    db_task = ExtractionTask(
        id=task_id,
        status="pending",
        field_notes=request.field_notes
    )
    db.add(db_task)
    db.commit()
    
    # Run the processing logic in the background
    background_tasks.add_task(process_extraction_task, task_id, request.field_notes)
    
    return ExtractAcceptedResponse(task_id=task_id, status="pending")


@app.get("/api/v1/extract/tasks/{task_id}", response_model=TaskResponse, tags=["GenAI Extractor"])
def get_extraction_task_status(task_id: str, db: Session = Depends(get_db)):
    task = db.query(ExtractionTask).filter(ExtractionTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    extracted_dict = None
    if task.extracted_data:
        try:
            extracted_dict = json.loads(task.extracted_data)
        except Exception:
            extracted_dict = {"raw": task.extracted_data}

    return TaskResponse(
        task_id=task.id,
        status=task.status,
        field_notes=task.field_notes,
        extracted_data=extracted_dict
    )
