from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import requests
import agent # HIPAA compliance agent
import os

app = FastAPI()

BILLING_API_URL = os.getenv("BILLING_API_URL", "https://localhost:8002/process-payment")

class BillPatientRequest(BaseModel):
    patient_id: str
    amount: float

@app.post("/bill-patient")
def bill_patient(request: BillPatientRequest):
    # 1. Perform HIPAA Compliance Check on Billing API
    print(f"[*] Performing HIPAA checks for Billing API: {BILLING_API_URL}...")
    
    # We need to check the base URL or just the endpoint. 
    # agent.check_tls_version expects a URL.
    tls_ok = agent.check_tls_version(BILLING_API_URL)
    auth_ok = agent.check_authentication(BILLING_API_URL)

    if not (tls_ok and auth_ok):
        raise HTTPException(status_code=400, detail="Billing API failed HIPAA compliance checks")

    # 2. If compliant, send payment request
    payload = {
        "patient_id": request.patient_id,
        "amount": request.amount,
        "currency": "USD"
    }
    headers = {"Authorization": "Bearer billing-secret-token"}
    
    try:
        # Suppress verify=False warning for self-signed certs in demo
        requests.packages.urllib3.disable_warnings()
        response = requests.post(BILLING_API_URL, json=payload, headers=headers, verify=False)
        
        if response.status_code == 200:
            return response.json()
        else:
            raise HTTPException(status_code=response.status_code, detail=f"Billing failed: {response.text}")
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error contacting billing API: {e}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8003)
