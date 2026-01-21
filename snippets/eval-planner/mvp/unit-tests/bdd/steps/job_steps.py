from behave import given, when, then
from database import SessionLocal, Agent, EvalRule, Job
from main import create_agent, create_job, AgentCreate, JobCreate
import uuid

# We need a db session key in context? 
# For unit-level BDD, we can mock or use a test DB. 
# Since we have a 'environment.py' that sets PYTHONPATH, let's use the actual DB models but maybe rollback?
# For simplicity in this environment, we'll create a dedicated session.

@given('an Agent named "{name}" with URL "{url}"')
def step_create_agent(context, name, url):
    db = SessionLocal()
    agent = Agent(name=name, url=url, auth_config={})
    db.add(agent)
    db.commit()
    db.refresh(agent)
    context.agent_id = agent.id
    db.close()

@given('a Rule named "{name}" with content')
def step_create_rule(context, name):
    db = SessionLocal()
    content = context.text
    rule = EvalRule(name=name, code_content=content, rule_type="PYTHON")
    db.add(rule)
    db.commit()
    db.refresh(rule)
    context.rule_id = rule.id
    db.close()

@when('I create a job binding "{rule_name}" to "{agent_name}"')
def step_create_job(context, rule_name, agent_name):
    # In a real test we might lookup by name, here we rely on the context IDs we just set
    # assuming sequential execution of proper steps
    db = SessionLocal()
    job = Job(rule_id=context.rule_id, agent_id=context.agent_id)
    db.add(job)
    db.commit()
    db.refresh(job)
    context.job_id = job.id
    context.job_status = job.status
    db.close()

@given('a Job exists for Rule "{rule_name}" and Agent "{agent_name}"')
def step_job_exists(context, rule_name, agent_name):
    db = SessionLocal()
    # Ensure agent and rule exist (reusing existing steps or creating here)
    agent = db.query(Agent).filter(Agent.name == agent_name).first()
    if not agent:
        agent = Agent(name=agent_name, url="http://test:8080")
        db.add(agent)
    
    rule = db.query(EvalRule).filter(EvalRule.name == rule_name).first()
    if not rule:
        rule = EvalRule(name=rule_name, code_content="async def evaluate(u,a,c): return {'passed': True}")
        db.add(rule)
    
    db.commit()
    
    job = Job(rule_id=rule.id, agent_id=agent.id)
    db.add(job)
    db.commit()
    db.refresh(job)
    context.job_id = job.id
    db.close()

@when('I execute the job')
def step_execute_job(context):
    # In the actual MVP, creation triggers execution via background tasks.
    # For BDD, we can call the executor logic directly or simulates it.
    from eval_runner import execute_job
    import asyncio
    db = SessionLocal()
    # We run it synchronously for the test
    asyncio.run(execute_job(context.job_id, db))
    db.close()

@then('the job should be created successfuly')
def step_check_job_created(context):
    assert context.job_id is not None

@then('the job status should be "{expected_status}"')
def step_check_job_status(context, expected_status):
    db = SessionLocal()
    job = db.query(Job).filter(Job.id == context.job_id).first()
    assert job.status == expected_status
    db.close()

@then('the job should link to "{agent_name}"')
def step_check_job_link(context, agent_name):
    db = SessionLocal()
    job = db.query(Job).filter(Job.id == context.job_id).first()
    agent = db.query(Agent).filter(Agent.id == job.agent_id).first()
    assert agent.name == agent_name
    db.close()

@then('the job status should eventually be "{expected_status}"')
def step_check_job_status_eventually(context, expected_status):
    import time
    db = SessionLocal()
    for _ in range(5):
        db.expire_all()
        job = db.query(Job).filter(Job.id == context.job_id).first()
        if job.status == expected_status:
            break
        time.sleep(0.5)
    assert job.status == expected_status
    db.close()

@then('an evaluation result should be recorded')
def step_check_eval_result(context):
    from database import EvalResult
    db = SessionLocal()
    result = db.query(EvalResult).filter(EvalResult.job_id == context.job_id).first()
    assert result is not None
    db.close()
