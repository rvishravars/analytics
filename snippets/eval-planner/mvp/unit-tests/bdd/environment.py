import sys
import os

def before_all(context):
    # Add backend source to path so we can import validation module
    # Assuming run from mvp/unit-tests/bdd/
    backend_path = os.path.abspath(os.path.join(os.getcwd(), "../../source/backend"))
    sys.path.append(backend_path)
    
    from database import init_db
    init_db()

def before_scenario(context, scenario):
    from database import SessionLocal, Agent, EvalRule, Job, EvalResult
    db = SessionLocal()
    try:
        db.query(EvalResult).delete()
        db.query(Job).delete()
        db.query(Agent).delete()
        db.query(EvalRule).delete()
        db.commit()
    finally:
        db.close()
