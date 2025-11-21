from fastapi import FastAPI, Header, HTTPException, Depends
import uvicorn
from pydantic import BaseModel

app = FastAPI()

class PaymentRequest(BaseModel):
    patient_id: str
    amount: float
    currency: str

# Authentication dependency
async def verify_token(authorization: str = Header(None)):
    if authorization is None:
        raise HTTPException(status_code=401, detail="Missing Authorization Header")
    
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=401, detail="Invalid Authorization Header Format")
    
    token = parts[1]
    if token != "billing-secret-token":
        raise HTTPException(status_code=401, detail="Invalid Token")
    
    return token

@app.api_route("/process-payment", methods=["GET", "POST"])
async def process_payment(payment: PaymentRequest = None, token: str = Depends(verify_token)):
    if payment is None:
         # If GET request (or POST without body), we still expect auth.
         # If auth passes (token is valid), we might return 405 or 400 here because body is missing.
         # But verify_token runs first. If no token, it raises 401.
         # So if we get here, token is valid.
         raise HTTPException(status_code=405, detail="Method Not Allowed")
    
    # Mock payment processing
    return {
        "status": "processed",
        "transaction_id": "txn_987654321",
        "amount": payment.amount,
        "currency": payment.currency
    }

@app.get("/")
async def root():
    return {"message": "Mock Billing API Running"}

if __name__ == "__main__":
    # Runs on HTTPS
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=8002,
        ssl_keyfile="key.pem", 
        ssl_certfile="cert.pem"
    )
