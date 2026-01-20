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
    rule_type: str = "PYTHON"

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

    db.delete(db_rule)
    db.commit()
    return {"ok": True}

# Agent & Job Models
class AgentBase(BaseModel):
    name: str
    url: str
    auth_config: Optional[dict] = {}

class AgentCreate(AgentBase):
    pass

class AgentResponse(AgentBase):
    id: UUID
    created_at: datetime

    class Config:
        from_attributes = True

class JobCreate(BaseModel):
    rule_id: UUID
    agent_id: UUID
    config_overrides: Optional[dict] = {}

class JobResponse(BaseModel):
    id: UUID
    status: str
    created_at: datetime
    rule_id: UUID
    agent_id: UUID

    class Config:
        from_attributes = True

@app.post("/api/agents", response_model=AgentResponse)
def create_agent(agent: AgentCreate, db: Session = Depends(get_db)):
    db_agent = database.Agent(name=agent.name, url=agent.url, auth_config=agent.auth_config)
    try:
        db.add(db_agent)
        db.commit()
        db.refresh(db_agent)
        return db_agent
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/agents", response_model=List[AgentResponse])
def read_agents(skip: int = 0, limit: int = 50, db: Session = Depends(get_db)):
    agents = db.query(database.Agent).offset(skip).limit(limit).all()
    return agents

@app.post("/api/jobs", response_model=JobResponse)
def create_job(job: JobCreate, db: Session = Depends(get_db)):
    # Verify rule and agent exist
    rule = db.query(database.EvalRule).filter(database.EvalRule.id == job.rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    agent = db.query(database.Agent).filter(database.Agent.id == job.agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    db_job = database.Job(rule_id=job.rule_id, agent_id=job.agent_id, config_overrides=job.config_overrides)
    db.add(db_job)
    db.commit()
    db.refresh(db_job)
    return db_job

@app.get("/api/jobs", response_model=List[JobResponse])
def read_jobs(skip: int = 0, limit: int = 50, db: Session = Depends(get_db)):
    jobs = db.query(database.Job).offset(skip).limit(limit).all()
    return jobs
