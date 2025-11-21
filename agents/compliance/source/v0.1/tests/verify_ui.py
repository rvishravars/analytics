import requests
import time
import sys

REQUESTER_URL = "http://localhost:8001"
TARGET_URL = "https://localhost:8000/secure-data"
CLIENT_ID = "ui-test-client"

def verify_ui():
    print("[*] Creating Subscription for UI Test...")
    payload = {
        "client_id": CLIENT_ID,
        "target_url": TARGET_URL
    }
    try:
        # Create subscription
        requests.post(f"{REQUESTER_URL}/subscribe", json=payload)
        
        # Fetch UI
        print("[*] Fetching Subscription List UI...")
        response = requests.get(f"{REQUESTER_URL}/subscriptions")
        
        if response.status_code == 200 and "text/html" in response.headers["content-type"]:
            print("    [PASS] UI endpoint returned 200 OK with HTML content.")
            
            content = response.text
            if "Active Subscriptions" in content and CLIENT_ID in content:
                print("    [PASS] UI contains expected title and client ID.")
                return True
            else:
                print("    [FAIL] UI content missing expected strings.")
                print(f"    Content preview: {content[:200]}...")
                return False
        else:
            print(f"    [FAIL] UI endpoint returned {response.status_code} or invalid content type.")
            return False
            
    except Exception as e:
        print(f"    [FAIL] UI verification error: {e}")
        return False

def main():
    # Wait for servers to start
    time.sleep(5)
    
    if verify_ui():
        print("\nOVERALL STATUS: PASS")
        sys.exit(0)
    else:
        print("\nOVERALL STATUS: FAIL")
        sys.exit(1)

if __name__ == "__main__":
    main()
