from sqlalchemy import create_engine, Column, String, Text, DateTime, text, ForeignKey, Uuid
from sqlalchemy.types import JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
import uuid
from datetime import datetime

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@db:5432/eval_db")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

class EvalRule(Base):
    __tablename__ = "evaluation_rules"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    name = Column(String(255), unique=True, index=True, nullable=False)
    description = Column(Text, nullable=True)
    code_content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    rule_type = Column(String, default="PYTHON", nullable=False)

class Agent(Base):
    __tablename__ = "agents"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    name = Column(String(255), unique=True, index=True, nullable=False)
    url = Column(String, nullable=False)
    auth_config = Column(JSON, default={}) # e.g. {"headers": {"Authorization": "Bearer..."}}
    created_at = Column(DateTime, default=datetime.utcnow)

class Job(Base):
    __tablename__ = "jobs"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    rule_id = Column(Uuid, ForeignKey("evaluation_rules.id"))
    agent_id = Column(Uuid, ForeignKey("agents.id"))
    status = Column(String, default="PENDING") # PENDING, RUNNING, COMPLETED, FAILED
    config_overrides = Column(JSON, default={})
    created_at = Column(DateTime, default=datetime.utcnow)

class EvalResult(Base):
    __tablename__ = "eval_results"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    job_id = Column(Uuid, ForeignKey("jobs.id"), nullable=False)
    status = Column(String, nullable=False) # SUCCESS, FAILED
    output = Column(JSON, default={})
    error = Column(Text, nullable=True)
    started_at = Column(DateTime, nullable=False)
    completed_at = Column(DateTime, nullable=False)



def init_db():
    Base.metadata.create_all(bind=engine)
