import requests
import time
import sys
import json

BASE_URL = "http://localhost:8000"

def log(msg):
    print(f"[TEST] {msg}")

def check_server():
    try:
        response = requests.get(f"{BASE_URL}/docs")
        if response.status_code == 200:
            log("Server is up and running.")
            return True
    except requests.exceptions.ConnectionError:
        log("Server is NOT reachable.")
        return False
    return False

def test_deep_scan():
    log("Starting Deep Scan test...")
    # This might take a while, so we set a generous timeout
    try:
        start_time = time.time()
        response = requests.post(f"{BASE_URL}/api/v1/search/scan", timeout=300)
        duration = time.time() - start_time
        
        if response.status_code == 200:
            data = response.json()
            log(f"Deep Scan completed in {duration:.2f}s")
            log(f"Response: {json.dumps(data, indent=2)}")
            return data.get("new_records", 0)
        else:
            log(f"Deep Scan failed with status {response.status_code}: {response.text}")
            return -1
    except Exception as e:
        log(f"Deep Scan exception: {str(e)}")
        return -1

def test_catalog():
    log("Checking Catalog Endpoint with Filters...")
    try:
        # Test basic list
        res = requests.get(f"{BASE_URL}/api/v1/search/catalog?limit=5")
        if res.status_code == 200:
            data = res.json()
            log(f"Catalog (basic): OK - {len(data)} items returned")
            
            # Test filter
            res_filter = requests.get(f"{BASE_URL}/api/v1/search/catalog?term=estupro&limit=5")
            if res_filter.status_code == 200:
                data_filter = res_filter.json()
                log(f"Catalog (filter 'estupro'): OK - {len(data_filter)} items returned")
            else:
                log(f"Catalog filter failed: {res_filter.status_code}")

            return len(data)
        else:
            log(f"Catalog failed: {res.status_code}")
            return -1
    except Exception as e:
        log(f"Catalog error: {e}")
        return -1

def test_geo_stats():
    log("Fetching Geo Stats...")
    try:
        # Basic
        res = requests.get(f"{BASE_URL}/api/v1/stats/geo")
        if res.status_code == 200:
            data = res.json()
            log(f"Geo stats fetched. Total points: {len(data)}")
            
            # Filter
            res_filter = requests.get(f"{BASE_URL}/api/v1/stats/geo?term=estupro")
            if res_filter.status_code == 200:
                data_filter = res_filter.json()
                log(f"Geo stats (filter 'estupro'): {len(data_filter)} points")
            
            return len(data)
        else:
            log(f"Geo stats failed: {res.status_code}")
            return -1
    except Exception as e:
        log(f"Geo stats error: {e}")
        return -1

def main():
    if not check_server():
        log("Please start the server first!")
        sys.exit(1)

    # 1. Run Deep Scan
    new_records = test_deep_scan()
    
    # 2. Verify Persistence
    if new_records >= 0:
        catalog_count = test_catalog()
        geo_count = test_geo_stats()
        
        if catalog_count > 0 and geo_count > 0:
            log("SUCCESS: System validation passed!")
        elif new_records == 0 and catalog_count >= 0:
             log("WARNING: Deep scan found 0 records (might be expected if no news found), but catalog is accessible.")
        else:
            log("FAILURE: System validation failed. Check logs.")
    else:
        log("FAILURE: Deep scan failed.")

if __name__ == "__main__":
    main()
