from fastapi import FastAPI, HTTPException, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
from uuid import UUID
from datetime import datetime
import database

app = FastAPI(title="Eval Planner Control Plane API")

# Dependency
def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Pydantic Models
class RuleBase(BaseModel):
    name: str
    description: Optional[str] = None
    code_content: str

class RuleCreate(RuleBase):
    pass

class RuleUpdate(RuleBase):
    pass

class RuleResponse(RuleBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# Init DB on startup
@app.on_event("startup")
def startup_event():
    database.init_db()

# Routes
@app.post("/api/rules", response_model=RuleResponse)
def create_rule(rule: RuleCreate, db: Session = Depends(get_db)):
    db_rule = database.EvalRule(**rule.dict())
    try:
        db.add(db_rule)
        db.commit()
        db.refresh(db_rule)
        return db_rule
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/rules", response_model=List[RuleResponse])
def list_rules(skip: int = 0, limit: int = 50, db: Session = Depends(get_db)):
    rules = db.query(database.EvalRule).offset(skip).limit(limit).all()
    return rules

@app.get("/api/rules/{rule_id}", response_model=RuleResponse)
def get_rule(rule_id: UUID, db: Session = Depends(get_db)):
    rule = db.query(database.EvalRule).filter(database.EvalRule.id == rule_id).first()
    if rule is None:
        raise HTTPException(status_code=404, detail="Rule not found")
    return rule

@app.put("/api/rules/{rule_id}", response_model=RuleResponse)
def update_rule(rule_id: UUID, rule_update: RuleUpdate, db: Session = Depends(get_db)):
    db_rule = db.query(database.EvalRule).filter(database.EvalRule.id == rule_id).first()
    if db_rule is None:
        raise HTTPException(status_code=404, detail="Rule not found")
    
    db_rule.name = rule_update.name
    db_rule.description = rule_update.description
    db_rule.code_content = rule_update.code_content
    
    try:
        db.commit()
        db.refresh(db_rule)
        return db_rule
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

@app.delete("/api/rules/{rule_id}")
def delete_rule(rule_id: UUID, db: Session = Depends(get_db)):
    db_rule = db.query(database.EvalRule).filter(database.EvalRule.id == rule_id).first()
    if db_rule is None:
        raise HTTPException(status_code=404, detail="Rule not found")
    
    db.delete(db_rule)
    db.commit()
    return {"ok": True}
