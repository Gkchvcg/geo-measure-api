import requests
import time
import json

base_url = "http://127.0.0.1:8000/api/files"

# 1. Upload KML
with open("sample.kml", "rb") as f:
    files = {"file": ("sample.kml", f, "application/vnd.google-earth.kml+xml")}
    res = requests.post(f"{base_url}/", files=files)
    
print("Upload:", res.json())
file_id = res.json()["id"]

# 2. Poll for info
for _ in range(5):
    res = requests.get(f"{base_url}/{file_id}/")
    info = res.json()
    print("Info:", info)
    if info["status"] == "COMPLETED":
        break
    time.sleep(1)
    
# 3. Get measurements
res = requests.get(f"{base_url}/{file_id}/measurements/")
print("Measurements:")
print(json.dumps(res.json(), indent=2))
