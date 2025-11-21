from fastapi import FastAPI, Header, HTTPException, Depends
from fastapi.responses import JSONResponse
import uvicorn
import ssl

app = FastAPI()

# Mock data store
MOCK_DATA = {"patient_id": "12345", "status": "healthy", "last_visit": "2023-10-27"}

# Authentication dependency
async def verify_token(authorization: str = Header(None)):
    if authorization is None:
        raise HTTPException(status_code=401, detail="Missing Authorization Header")
    
    # Expecting "Bearer <token>"
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=401, detail="Invalid Authorization Header Format")
    
    token = parts[1]
    if token != "valid-secret-token":
        raise HTTPException(status_code=401, detail="Invalid Token")
    
    return token

@app.get("/secure-data")
async def get_secure_data(token: str = Depends(verify_token)):
    return MOCK_DATA

@app.get("/")
async def root():
    return {"message": "HIPAA Mock Server Running"}

if __name__ == "__main__":
    # In a real scenario, we'd use a proper WSGI/ASGI server config, 
    # but for this agent test, we run uvicorn directly with ssl context.
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=8000,
        ssl_keyfile="key.pem",
        ssl_certfile="cert.pem"
    )
