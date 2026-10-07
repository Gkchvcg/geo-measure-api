import os
import uuid
import json
from app.services.geo_service import GeoProcessor

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

class FileService:
    def __init__(self):
        # We will use a simple file-based JSON store for our "database"
        self.db_path = os.path.join(UPLOAD_DIR, "db.json")
        if not os.path.exists(self.db_path):
            with open(self.db_path, "w") as f:
                json.dump({}, f)
                
    def _read_db(self):
        with open(self.db_path, "r") as f:
            return json.load(f)
            
    def _write_db(self, data):
        with open(self.db_path, "w") as f:
            json.dump(data, f)
            
    def save_upload_info(self, file_id: str, filename: str):
        db = self._read_db()
        db[file_id] = {
            "id": file_id,
            "filename": filename,
            "status": "PROCESSING"
        }
        self._write_db(db)
        
    def update_file_info(self, file_id: str, data: dict):
        db = self._read_db()
        if file_id in db:
            db[file_id].update(data)
            self._write_db(db)
            
    def get_file_info(self, file_id: str):
        db = self._read_db()
        return db.get(file_id)

    async def process_file(self, file_id: str, file_path: str, original_filename: str):
        try:
            processor = GeoProcessor(file_path, original_filename)
            processor.process()
            
            measurements = processor.calculate_measurements()
            
            # Save measurements to a separate JSON file
            meas_path = os.path.join(UPLOAD_DIR, f"{file_id}_measurements.json")
            with open(meas_path, "w") as f:
                json.dump(measurements, f)
                
            self.update_file_info(file_id, {
                "status": "COMPLETED",
                "feature_count": len(processor.features),
                "crs": processor.crs_name
            })
        except Exception as e:
            self.update_file_info(file_id, {
                "status": "FAILED",
                "error": str(e)
            })

    def get_measurements(self, file_id: str):
        meas_path = os.path.join(UPLOAD_DIR, f"{file_id}_measurements.json")
        if os.path.exists(meas_path):
            with open(meas_path, "r") as f:
                return json.load(f)
        return None
