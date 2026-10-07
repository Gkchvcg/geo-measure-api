# Geospatial File Measurement API

A backend service built with FastAPI that accepts geospatial files (Shapefile in `.zip` or `.kml`), processes the features within them, and returns geometry measurements.

## Setup

1. **Clone the repository and enter the directory**:
   ```bash
   git clone <repo-url>
   cd geo-measure-api
   ```

2. **Create a virtual environment and install dependencies**:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

3. **Run the application**:
   ```bash
   uvicorn app.main:app --host 127.0.0.1 --port 8000
   ```
   The API will be available at `http://127.0.0.1:8000`

## API Documentation

### 1. Upload File
Uploads and processes a `.zip` (containing a shapefile) or `.kml` file. The processing happens in the background.

**Endpoint**: `POST /api/files/`

**Request**:
`multipart/form-data` with a `file` field.

**Response**:
```json
{
  "message": "File uploaded successfully",
  "id": "4a40b8e4-60df-449d-af56-2dd7c92c7fa5"
}
```

### 2. File Information
Returns information about the uploaded file including processing status.

**Endpoint**: `GET /api/files/{id}/`

**Response**:
```json
{
  "id": "4a40b8e4-60df-449d-af56-2dd7c92c7fa5",
  "filename": "sample.kml",
  "feature_count": 3,
  "crs": "EPSG:4326",
  "status": "COMPLETED"
}
```

### 3. Measurements
Returns geometry measurements for the features in the file.

**Endpoint**: `GET /api/files/{id}/measurements/`

**Response**:
```json
{
  "file_id": "4a40b8e4-60df-449d-af56-2dd7c92c7fa5",
  "measurements": [
    {
      "feature_id": 0,
      "geometry_type": "Polygon",
      "measurement_type": "Area",
      "value": 15.718571942299604
    },
    {
      "feature_id": 1,
      "geometry_type": "LineString",
      "measurement_type": "Length",
      "value": 5.678457931186478
    },
    {
      "feature_id": 2,
      "geometry_type": "Point",
      "measurement_type": null,
      "value": null
    }
  ]
}
```

## Architecture

### Application Structure
- `app/main.py`: Entry point for the FastAPI application defining all routes.
- `app/models/schemas.py`: Pydantic models for request/response serialization and validation.
- `app/services/file_service.py`: Handles saving uploaded files, tracking metadata and background job state in a simple JSON store, and orchestrating the background processing.
- `app/services/geo_service.py`: Contains the core logic for parsing KML and Shapefiles (via `.zip`), handling Coordinate Reference Systems (CRS), and calculating measurements.

### File-Processing Flow
1. Client uploads a file via POST `/api/files/`.
2. The file is streamed and saved to disk.
3. Metadata is saved to `db.json` with a `PROCESSING` status.
4. A background task (`FastAPI BackgroundTasks`) is spawned to extract and parse the file using `GeoProcessor`.
5. Upon completion, measurements are generated and saved to `<file_id>_measurements.json`, and the file status is updated to `COMPLETED`. 

### Measurement Calculation Flow
1. Features (geometries and properties) are extracted using `pyshp` (for Shapefiles) or `xml.etree.ElementTree` (for KML).
2. The original geometries are modeled as `shapely` geometric objects.
3. If the file geometry is a Polygon, its **Area** is calculated. For LineString, its **Length** is computed. Points are omitted from measurements.
4. Calculations are delegated to `pyproj.Geod`, which relies on transforming geometries correctly as per the CRS.

### CRS Handling
1. KML is assumed `EPSG:4326` by specification.
2. Shapefile `.prj` files are read and parsed to a `pyproj.CRS` object if available.
3. Geometries are reprojected from their native CRS (if not WGS84) to `EPSG:4326` using `pyproj.Transformer`.
4. Then `pyproj.Geod` uses WGS84 coordinates to compute highly accurate geodesic area and length over the WGS84 ellipsoid. This prevents distortions normally caused by flat map projections (like Web Mercator) globally.

## Design Decisions
- **Avoided heavy GDAL dependency**: Using `shapely`, `pyproj`, `pyshp` directly ensures the service can be easily containerized or run anywhere without complex system-level dependencies like GDAL (which sometimes makes standard `geopandas`/`fiona` difficult to install). 
- **Background Processing**: File processing for large geospatial files can take time. Thus, processing runs as a background task.
- **Geodesic Measurements**: Rather than projecting everything into an equal-area or equidistant planar CRS which might only be accurate locally, the choice to use `pyproj.Geod(ellps="WGS84")` offers excellent, globally consistent measurement calculations for lengths and areas directly on the ellipsoid.

## Learning and Future Scope
### Learning
- Implementing a robust yet lightweight geospatial ingestion pipeline without heavy bindings like GDAL. 
- Using standard `pyproj` logic combined with ellipsoid geometry to solve global measurement distortions efficiently.

### Future Scope
- Switch the simple `db.json` file system DB to a robust database like PostgreSQL with PostGIS for spatial queries.
- Support storing data to an S3 object store instead of local disk.
- Implement Celery + Redis for a scalable distributed task queue to handle thousands of large files concurrently.
- Improve file format support (GeoJSON, GeoTIFF, etc.) and add bounding box (BBOX) outputs.
