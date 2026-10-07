import os
import zipfile
import tempfile
import xml.etree.ElementTree as ET
import shapefile
from pyproj import CRS, Transformer
from shapely.geometry import shape, Point, LineString, Polygon, MultiPolygon
from shapely.ops import transform

class GeoProcessor:
    def __init__(self, file_path: str, original_filename: str):
        self.file_path = file_path
        self.original_filename = original_filename.lower()
        self.features = []
        self.crs_wkt = None
        self.crs_name = "EPSG:4326"  # Default
        
    def process(self):
        if self.original_filename.endswith(".zip"):
            self._process_shapefile_zip()
        elif self.original_filename.endswith(".kml"):
            self._process_kml()
        else:
            raise ValueError("Unsupported file format")
            
    def _process_shapefile_zip(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with zipfile.ZipFile(self.file_path, 'r') as zip_ref:
                zip_ref.extractall(tmpdir)
                
            shp_file = None
            prj_file = None
            for root, dirs, files in os.walk(tmpdir):
                for f in files:
                    if f.endswith('.shp'):
                        shp_file = os.path.join(root, f)
                    elif f.endswith('.prj'):
                        prj_file = os.path.join(root, f)
            
            if not shp_file:
                raise ValueError("No .shp file found in the zip archive")
                
            if prj_file:
                with open(prj_file, 'r') as f:
                    self.crs_wkt = f.read()
                    try:
                        crs = CRS.from_wkt(self.crs_wkt)
                        self.crs_name = f"{crs.to_authority()[0]}:{crs.to_authority()[1]}" if crs.to_authority() else crs.name
                    except:
                        pass
            
            sf = shapefile.Reader(shp_file)
            for i, shape_rec in enumerate(sf.shapeRecords()):
                geom = shape_rec.shape.__geo_interface__
                if not geom or geom.get('type') == 'Null':
                    continue
                self.features.append({
                    "id": i,
                    "geometry": geom,
                    "properties": shape_rec.record.as_dict()
                })
                
    def _process_kml(self):
        self.crs_name = "EPSG:4326"
        tree = ET.parse(self.file_path)
        root = tree.getroot()
        
        # KML namespaces
        namespaces = {'kml': 'http://www.opengis.net/kml/2.2'}
        
        # We'll just do a very basic parsing for Placemarks
        features = []
        for i, placemark in enumerate(root.findall('.//kml:Placemark', namespaces)):
            name_elem = placemark.find('kml:name', namespaces)
            name = name_elem.text if name_elem is not None else f"Feature_{i}"
            
            geom = None
            
            # Point
            point = placemark.find('.//kml:Point/kml:coordinates', namespaces)
            if point is not None:
                coords = self._parse_coords(point.text)
                if coords:
                    geom = {"type": "Point", "coordinates": coords[0]}
            
            # LineString
            line = placemark.find('.//kml:LineString/kml:coordinates', namespaces)
            if line is not None:
                coords = self._parse_coords(line.text)
                if coords:
                    geom = {"type": "LineString", "coordinates": coords}
                    
            # Polygon
            polygon = placemark.find('.//kml:Polygon/kml:outerBoundaryIs/kml:LinearRing/kml:coordinates', namespaces)
            if polygon is not None:
                coords = self._parse_coords(polygon.text)
                if coords:
                    geom = {"type": "Polygon", "coordinates": [coords]}
                    
            if geom:
                self.features.append({
                    "id": i,
                    "geometry": geom,
                    "properties": {"name": name}
                })

    def _parse_coords(self, text: str):
        if not text:
            return []
        coords = []
        for pair in text.strip().split():
            parts = [float(p) for p in pair.split(',')]
            if len(parts) >= 2:
                coords.append((parts[0], parts[1]))
        return coords

    def calculate_measurements(self):
        measurements = []
        
        # Best guess for an equal-area or appropriate projected CRS based on bounds could be complex.
        # An easy approach: project EPSG:4326 to Web Mercator (EPSG:3857) or to a local UTM.
        # But for accurate area globally without determining UTM zone, an equal area projection like Mollweide or Lambert Azimuthal Equal Area is better.
        # Let's project to World Mollweide (EPSG:54009) or just use local UTM if we want to be fancy.
        # The easiest acceptable approach for a challenge is just to project to EPSG:3857 (Web Mercator) though it distorts area, 
        # or better: project to an Azimuthal Equidistant centered on the geometry centroid, or just Global Mollweide (ESRI:54009).
        # We'll use EPSG:6933 (WGS 84 / NSIDC EASE-Grid 2.0 Global) for area, or local UTM.
        # For simplicity, let's just project to EPSG:3857. It's often used, despite distortion, or we can use the `pyproj.Geod` directly on WGS84 for accurate measurements!
        
        geod = CRS("EPSG:4326").get_geod()
        
        try:
            # If there's a custom CRS, maybe try to create a transformer to EPSG:4326 first
            if self.crs_wkt:
                source_crs = CRS.from_wkt(self.crs_wkt)
            else:
                source_crs = CRS.from_string(self.crs_name)
                
            project_to_wgs84 = Transformer.from_crs(source_crs, CRS("EPSG:4326"), always_xy=True).transform
        except Exception:
            project_to_wgs84 = lambda x, y: (x, y) # fallback

        for feat in self.features:
            geom_dict = feat["geometry"]
            try:
                s_geom = shape(geom_dict)
                # Ensure it's in WGS84 for the Geod calculation
                s_geom_wgs84 = transform(project_to_wgs84, s_geom)
                
                geom_type = geom_dict["type"]
                measurement_type = None
                value = None
                
                if geom_type in ["Polygon", "MultiPolygon"]:
                    # Area in square meters using Geod (highly accurate on ellipsoid)
                    # geod.geometry_area_perimeter returns (area, perimeter)
                    area, _ = geod.geometry_area_perimeter(s_geom_wgs84)
                    value = abs(area)
                    measurement_type = "Area"
                elif geom_type in ["LineString", "MultiLineString"]:
                    # Length in meters
                    value = geod.geometry_length(s_geom_wgs84)
                    measurement_type = "Length"
                
                measurements.append({
                    "feature_id": feat["id"],
                    "geometry_type": geom_type,
                    "measurement_type": measurement_type,
                    "value": value
                })
            except Exception as e:
                # Handle geometries that can't be processed gracefully
                measurements.append({
                    "feature_id": feat["id"],
                    "geometry_type": geom_dict.get("type", "Unknown"),
                    "measurement_type": None,
                    "value": None
                })
                
        return measurements
