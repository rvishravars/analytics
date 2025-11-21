import requests
import time
import sys

REQUESTER_URL = "http://localhost:8001"
TARGET_URL = "https://localhost:8000/secure-data"
CLIENT_ID = "test-client-01"

def test_subscription():
    print("[*] Testing Subscription...")
    payload = {
        "client_id": CLIENT_ID,
        "target_url": TARGET_URL
    }
    try:
        response = requests.post(f"{REQUESTER_URL}/subscribe", json=payload)
        if response.status_code == 200:
            print("    [PASS] Subscription created successfully.")
            print(f"    Response: {response.json()}")
            return True
        else:
            print(f"    [FAIL] Subscription failed. Status: {response.status_code}, Detail: {response.text}")
            return False
    except Exception as e:
        print(f"    [FAIL] Subscription request error: {e}")
        return False

def test_data_request():
    print("\n[*] Testing Data Request (with Compliance Check)...")
    params = {
        "client_id": CLIENT_ID,
        "target_url": TARGET_URL
    }
    try:
        response = requests.post(f"{REQUESTER_URL}/request-data", params=params)
        if response.status_code == 200:
            print("    [PASS] Data request successful.")
            print(f"    Response: {response.json()}")
            return True
        else:
            print(f"    [FAIL] Data request failed. Status: {response.status_code}, Detail: {response.text}")
            return False
    except Exception as e:
        print(f"    [FAIL] Data request error: {e}")
        return False

def main():
    # Wait for servers to start
    time.sleep(5)
    
    sub_pass = test_subscription()
    req_pass = test_data_request()

    if sub_pass and req_pass:
        print("\nOVERALL STATUS: PASS")
        sys.exit(0)
    else:
        print("\nOVERALL STATUS: FAIL")
        sys.exit(1)

if __name__ == "__main__":
    main()
