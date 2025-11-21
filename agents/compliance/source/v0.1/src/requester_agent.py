from fastapi import FastAPI, HTTPException, Depends
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from database import SessionLocal, Subscription, init_db
import agent  # Import the HIPAA agent module

app = FastAPI()

# Initialize DB
init_db()

# Pydantic models
class SubscriptionCreate(BaseModel):
    client_id: str
    target_url: str

class SubscriptionResponse(BaseModel):
    id: int
    client_id: str
    target_url: str
    is_active: bool

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.post("/subscribe", response_model=SubscriptionResponse)
def create_subscription(subscription: SubscriptionCreate, db: Session = Depends(get_db)):
    # Check if subscription already exists
    existing = db.query(Subscription).filter(
        Subscription.client_id == subscription.client_id,
        Subscription.target_url == subscription.target_url
    ).first()
    
    if existing:
        return existing

    db_subscription = Subscription(
        client_id=subscription.client_id,
        target_url=subscription.target_url
    )
    db.add(db_subscription)
    db.commit()
    db.refresh(db_subscription)
    return db_subscription

@app.post("/request-data")
def request_data(client_id: str, target_url: str, db: Session = Depends(get_db)):
    # 1. Verify subscription
    sub = db.query(Subscription).filter(
        Subscription.client_id == client_id,
        Subscription.target_url == target_url,
        Subscription.is_active == True
    ).first()
    
    if not sub:
        raise HTTPException(status_code=403, detail="No active subscription found")

    # 2. Perform HIPAA Compliance Check
    print(f"[*] Performing HIPAA checks for {target_url}...")
    tls_ok = agent.check_tls_version(target_url)
    auth_ok = agent.check_authentication(target_url)

    if not (tls_ok and auth_ok):
        raise HTTPException(status_code=400, detail="Target endpoint failed HIPAA compliance checks")

    # 3. If compliant, proceed (Mocking data retrieval)
    return {
        "status": "success",
        "message": "Data retrieved successfully (Compliance Verified)",
        "data": {"mock_patient_data": "..."}
    }

@app.get("/subscriptions", response_class=HTMLResponse)
def list_subscriptions(db: Session = Depends(get_db)):
    subscriptions = db.query(Subscription).all()
    
    rows = ""
    for sub in subscriptions:
        rows += f"""
                <tr>
                    <td>{sub.id}</td>
                    <td>{sub.client_id}</td>
                    <td>{sub.target_url}</td>
                    <td>{sub.is_active}</td>
                    <td>{sub.created_at}</td>
                </tr>
        """
    
    html_content = f"""
    <html>
        <head>
            <title>Subscription List</title>
            <style>
                body {{ font-family: sans-serif; padding: 20px; }}
                table {{ border-collapse: collapse; width: 100%; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                th {{ background-color: #f2f2f2; }}
                tr:nth-child(even) {{ background-color: #f9f9f9; }}
                h1 {{ color: #333; }}
            </style>
        </head>
        <body>
            <h1>Active Subscriptions</h1>
            <table>
                <tr>
                    <th>ID</th>
                    <th>Client ID</th>
                    <th>Target URL</th>
                    <th>Active</th>
                    <th>Created At</th>
                </tr>
                {rows}
            </table>
        </body>
    </html>
    """
    return html_content


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
