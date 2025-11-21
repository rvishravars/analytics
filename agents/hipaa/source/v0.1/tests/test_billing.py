import requests
import time
import sys

BILLING_AGENT_URL = "http://localhost:8003"

def test_billing():
    print("[*] Testing Billing Agent...")
    payload = {
        "patient_id": "patient-123",
        "amount": 150.00
    }
    try:
        # The billing agent will check compliance of the billing server (port 8002)
        # and then process the payment.
        response = requests.post(f"{BILLING_AGENT_URL}/bill-patient", json=payload)
        
        if response.status_code == 200:
            print("    [PASS] Billing request successful.")
            print(f"    Response: {response.json()}")
            return True
        else:
            print(f"    [FAIL] Billing request failed. Status: {response.status_code}, Detail: {response.text}")
            return False
    except Exception as e:
        print(f"    [FAIL] Billing request error: {e}")
        return False

def main():
    # Wait for servers to start
    time.sleep(5)
    
    if test_billing():
        print("\nOVERALL STATUS: PASS")
        sys.exit(0)
    else:
        print("\nOVERALL STATUS: FAIL")
        sys.exit(1)

if __name__ == "__main__":
    main()
