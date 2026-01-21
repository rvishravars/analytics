import httpx
from datetime import datetime
from sqlalchemy.orm import Session
from uuid import UUID
import database
import json

async def execute_job(job_id: UUID, db: Session) -> database.EvalResult:
    """
    Execute a job by running the evaluation rule against the agent.
    
    Args:
        job_id: UUID of the job to execute
        db: Database session
        
    Returns:
        EvalResult object with execution results
    """
    # Get job details
    job = db.query(database.Job).filter(database.Job.id == job_id).first()
    if not job:
        raise ValueError(f"Job {job_id} not found")
    
    # Update job status to RUNNING
    job.status = "RUNNING"
    db.commit()
    
    # Get rule and agent
    rule = db.query(database.EvalRule).filter(database.EvalRule.id == job.rule_id).first()
    agent = db.query(database.Agent).filter(database.Agent.id == job.agent_id).first()
    
    if not rule:
        raise ValueError(f"Rule {job.rule_id} not found")
    if not agent:
        raise ValueError(f"Agent {job.agent_id} not found")
    
    started_at = datetime.utcnow()
    
    try:
        # Execute the rule code
        result_output = await run_rule_code(
            rule.code_content,
            agent.url,
            agent.auth_config,
            job.config_overrides
        )
        
        completed_at = datetime.utcnow()
        
        # Create result record
        eval_result = database.EvalResult(
            job_id=job_id,
            status="SUCCESS",
            output=result_output,
            error=None,
            started_at=started_at,
            completed_at=completed_at
        )
        
        # Update job status
        job.status = "COMPLETED"
        
    except Exception as e:
        completed_at = datetime.utcnow()
        
        # Create error result
        eval_result = database.EvalResult(
            job_id=job_id,
            status="FAILED",
            output={},
            error=str(e),
            started_at=started_at,
            completed_at=completed_at
        )
        
        # Update job status
        job.status = "FAILED"
    
    db.add(eval_result)
    db.commit()
    db.refresh(eval_result)
    
    return eval_result


async def run_rule_code(code: str, agent_url: str, auth_config: dict, config_overrides: dict) -> dict:
    """
    Execute the evaluation rule code.
    
    The code should define a function called 'evaluate' that takes agent_url, auth_config, and config as parameters.
    
    Args:
        code: Python code to execute
        agent_url: URL of the agent to test
        auth_config: Authentication configuration
        config_overrides: Configuration overrides from the job
        
    Returns:
        Dictionary with evaluation results
    """
    # Prepare execution context
    context = {
        'agent_url': agent_url,
        'auth_config': auth_config,
        'config': config_overrides,
        'call_agent': call_agent,
        'httpx': httpx,
        'json': json
    }
    
    # Execute the rule code
    exec(code, context)
    
    # Call the evaluate function
    if 'evaluate' not in context:
        raise ValueError("Rule code must define an 'evaluate' function")
    
    evaluate_func = context['evaluate']
    
    # Check if the function is async
    import inspect
    if inspect.iscoroutinefunction(evaluate_func):
        result = await evaluate_func(agent_url, auth_config, config_overrides)
    else:
        result = evaluate_func(agent_url, auth_config, config_overrides)
    
    return result


async def call_agent(url: str, payload: dict = None, auth: dict = None, method: str = "POST") -> dict:
    """
    Helper function to call an agent endpoint.
    
    Args:
        url: Full URL to call
        payload: Request payload (for POST/PUT)
        auth: Authentication config (headers)
        method: HTTP method
        
    Returns:
        Response as dictionary
    """
    headers = auth.get('headers', {}) if auth else {}
    
    async with httpx.AsyncClient() as client:
        if method.upper() == "GET":
            response = await client.get(url, headers=headers)
        elif method.upper() == "POST":
            response = await client.post(url, json=payload, headers=headers)
        elif method.upper() == "PUT":
            response = await client.put(url, json=payload, headers=headers)
        else:
            raise ValueError(f"Unsupported HTTP method: {method}")
        
        response.raise_for_status()
        return response.json()
