import os
import requests

ASSETS_DIR = "static/vendor/leaflet"
IMAGES_DIR = f"{ASSETS_DIR}/images"

FILES = {
    "leaflet.css": "https://unpkg.com/leaflet@1.9.4/dist/leaflet.css",
    "leaflet.js": "https://unpkg.com/leaflet@1.9.4/dist/leaflet.js",
    "images/layers.png": "https://unpkg.com/leaflet@1.9.4/dist/images/layers.png",
    "images/layers-2x.png": "https://unpkg.com/leaflet@1.9.4/dist/images/layers-2x.png",
    "images/marker-icon.png": "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png",
    "images/marker-icon-2x.png": "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png",
    "images/marker-shadow.png": "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png"
}

def download_file(url, path):
    print(f"Downloading {url} to {path}...")
    try:
        r = requests.get(url, verify=False) # Ignorar SSL para garantir download
        if r.status_code == 200:
            with open(path, 'wb') as f:
                f.write(r.content)
            print("Done.")
        else:
            print(f"Failed: {r.status_code}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    if not os.path.exists(IMAGES_DIR):
        os.makedirs(IMAGES_DIR)
        
    for filename, url in FILES.items():
        path = os.path.join(ASSETS_DIR, filename)
        download_file(url, path)
