"""
AI Vision Mock Service for B6 Core Business
Simulates YOLO/MediaPipe object detection
"""

from fastapi import FastAPI
from pydantic import BaseModel, UUID4
from typing import Optional, List
from datetime import datetime
import uuid
import os
import random

app = FastAPI(
    title="AI Vision Service",
    description="Mock AI service for object detection",
    version="1.0.0"
)


class DetectionRequest(BaseModel):
    correlationId: UUID4
    imageRef: str
    faceEmbedding: Optional[List[float]] = None
    detectionId: Optional[UUID4] = None


class DetectionResponse(BaseModel):
    detectionId: UUID4
    matched: bool
    label: str
    confidence: float
    status: str
    modelVersion: str
    processedAt: datetime


@app.get("/health")
async def health_check():
    return {
        "status": "UP",
        "model_loaded": True,
        "timestamp": datetime.now().isoformat()
    }


@app.post("/predict", response_model=DetectionResponse)
async def predict(request: DetectionRequest):
    # Simulate processing time
    import time
    time.sleep(0.05)
    
    image_lower = request.imageRef.lower()
    
    if "person" in image_lower or "face" in image_lower:
        confidence = random.uniform(0.75, 0.98)
        matched = confidence >= 0.7
        label = "person"
        status = "matched" if matched else "low_confidence"
    elif "smoke" in image_lower or "fire" in image_lower:
        confidence = random.uniform(0.85, 0.99)
        matched = True
        label = "fire"
        status = "matched"
    else:
        confidence = random.uniform(0.2, 0.5)
        matched = False
        label = "unknown"
        status = "not_matched"
    
    return DetectionResponse(
        detectionId=request.detectionId or uuid.uuid4(),
        matched=matched,
        label=label,
        confidence=confidence,
        status=status,
        modelVersion="yolov8n-mock-v1",
        processedAt=datetime.now()
    )


@app.get("/ready")
async def ready():
    return {"ready": True}
