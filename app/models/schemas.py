from pydantic import BaseModel
from typing import Optional, List, Union, Any, Dict

class FileInfo(BaseModel):
    id: str
    filename: str
    feature_count: int
    crs: Optional[str]
    status: str

class FeatureMeasurement(BaseModel):
    feature_id: Union[str, int]
    geometry_type: str
    measurement_type: Optional[str]
    value: Optional[float]

class FileMeasurements(BaseModel):
    file_id: str
    measurements: List[FeatureMeasurement]
