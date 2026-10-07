from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
import uuid
import os
import aiofiles

from app.models.schemas import FileInfo, FileMeasurements, FeatureMeasurement
from app.services.file_service import FileService, UPLOAD_DIR

app = FastAPI(title="Geospatial File Measurement API")
file_service = FileService()

@app.post("/api/files/", response_model=dict)
async def upload_file(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    if not (file.filename.endswith(".zip") or file.filename.endswith(".kml")):
        raise HTTPException(status_code=400, detail="Only .zip (Shapefile) or .kml files are supported.")
        
    file_id = str(uuid.uuid4())
    file_path = os.path.join(UPLOAD_DIR, f"{file_id}_{file.filename}")
    
    async with aiofiles.open(file_path, 'wb') as out_file:
        content = await file.read()
        await out_file.write(content)
        
    file_service.save_upload_info(file_id, file.filename)
    
    # Process the file in the background so the upload responds quickly
    background_tasks.add_task(file_service.process_file, file_id, file_path, file.filename)
    
    return {"message": "File uploaded successfully", "id": file_id}

@app.get("/api/files/{id}/", response_model=FileInfo)
async def get_file_info(id: str):
    info = file_service.get_file_info(id)
    if not info:
        raise HTTPException(status_code=404, detail="File not found")
        
    return FileInfo(
        id=info["id"],
        filename=info["filename"],
        feature_count=info.get("feature_count", 0),
        crs=info.get("crs"),
        status=info["status"]
    )

@app.get("/api/files/{id}/measurements/", response_model=FileMeasurements)
async def get_measurements(id: str):
    info = file_service.get_file_info(id)
    if not info:
        raise HTTPException(status_code=404, detail="File not found")
        
    if info["status"] != "COMPLETED":
        raise HTTPException(status_code=400, detail=f"File processing status is {info['status']}")
        
    measurements = file_service.get_measurements(id)
    if measurements is None:
        raise HTTPException(status_code=404, detail="Measurements not found")
        
    feature_measurements = [FeatureMeasurement(**m) for m in measurements]
    return FileMeasurements(file_id=id, measurements=feature_measurements)
