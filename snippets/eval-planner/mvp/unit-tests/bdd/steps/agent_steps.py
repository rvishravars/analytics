from behave import given, when, then
from database import SessionLocal, Agent
from main import create_agent, AgentCreate
import uuid

@when('I register an agent named "{name}" with URL "{url}"')
def step_register_agent(context, name, url):
    db = SessionLocal()
    agent_data = AgentCreate(name=name, url=url, auth_config={})
    db_agent = create_agent(agent_data, db)
    context.agent_id = db_agent.id
    db.close()

@then('the agent should be registered successfully')
def step_check_agent_registered(context):
    assert context.agent_id is not None

@then('I should see "{name}" in the agent registry')
def step_check_agent_in_registry(context, name):
    db = SessionLocal()
    agent = db.query(Agent).filter(Agent.name == name).first()
    assert agent is not None
    db.close()

@when('I list all registered agents')
def step_list_agents(context):
    db = SessionLocal()
    context.agents = db.query(Agent).all()
    db.close()

@then('I should find "{name1}" and "{name2}" in the list')
def step_check_agents_in_list(context, name1, name2):
    names = [a.name for a in context.agents]
    assert name1 in names
    assert name2 in names

@when('I request details for "{name}"')
def step_request_agent_details(context, name):
    db = SessionLocal()
    context.target_agent = db.query(Agent).filter(Agent.name == name).first()
    db.close()

@then('I should receive the correct URL "{url}"')
def step_check_agent_url(context, url):
    assert context.target_agent.url == url
