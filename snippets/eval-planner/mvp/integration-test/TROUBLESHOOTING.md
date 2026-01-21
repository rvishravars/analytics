# Pending Job Troubleshooting

## Issue
Job was staying in PENDING status, then failed with function signature error after execution.

## Root Causes Found

### 1. Sample Agent Not Running ✅ FIXED
After fresh deployment with `docker compose down -v`, the sample agent container was not started.

**Resolution**: Ran `sudo ./run_agent.sh` to start the sample agent.

### 2. Network Connectivity ✅ FIXED
The sample agent was not connected to the `source_default` network, preventing the backend from reaching it.

**Resolution**: Connected agent to network with:
```bash
sudo docker network connect source_default sample-agent-container
```

### 3. Incorrect Rule Function Signature ⚠️ NEEDS FIXING

Your rule code has this signature:
```python
def evaluate(ctx):
    return {"score": 1, "passed": True}
```

But the eval runner expects:
```python
async def evaluate(agent_url, auth_config, config):
    # Your evaluation logic here
    return {"score": 1, "passed": True}
```

## How to Fix Your Rule

### Option 1: Update the existing rule
```bash
curl -X PUT http://localhost:8000/api/rules/729fc223-ac60-487a-8299-0c3877656279 \
  -H "Content-Type: application/json" \
  -d '{
    "name": "test",
    "description": "test",
    "code_content": "async def evaluate(agent_url, auth_config, config):\n    import httpx\n    async with httpx.AsyncClient() as client:\n        response = await client.get(f\"{agent_url}/health\")\n        return {\"score\": 1, \"passed\": response.status_code == 200}\n",
    "rule_type": "PYTHON"
  }'
```

### Option 2: Create a new job with a proper rule
Use the test script:
```bash
cd /home/vishravars/code/learning/snippets/eval-planner/mvp/source/integration-test
./test_eval_execution.sh
```

## Required Function Signature

All evaluation rules MUST define a function with this signature:
```python
async def evaluate(agent_url: str, auth_config: dict, config: dict) -> dict:
    """
    Args:
        agent_url: The URL of the agent to evaluate
        auth_config: Authentication configuration from agent registration
        config: Config overrides from the job
    
    Returns:
        Dictionary with evaluation results
    """
    # Your evaluation logic here
    pass
```

## Quick Start Guide After Fresh Deployment

Whenever you run `docker compose down -v` and redeploy, you need to:

1. **Start the sample agent**:
   ```bash
   cd mvp/source/integration-test
   sudo ./run_agent.sh
   ```

2. **Connect it to the network**:
   ```bash
   sudo docker network connect source_default sample-agent-container
   ```

3. **Run the test or create proper rules**:
   ```bash
   ./test_eval_execution.sh
   ```
