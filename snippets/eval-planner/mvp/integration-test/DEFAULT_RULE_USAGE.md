# Creating Rules with Default Template

## Now when you create a rule, you can omit `code_content` and it will use a sensible default!

### Example 1: Create rule with default code
```bash
curl -X POST http://localhost:8000/api/rules \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Auto Health Check",
    "description": "Uses default health check evaluation"
  }'
```

This will automatically create a rule with the following code:
```python
async def evaluate(agent_url, auth_config, config):
    """
    Evaluation function that tests an agent.
    
    Args:
        agent_url: The URL of the agent to evaluate
        auth_config: Authentication configuration (e.g., {"headers": {"Authorization": "Bearer..."}})
        config: Configuration overrides from the job
    
    Returns:
        Dictionary with evaluation results
    """
    import httpx
    
    # Example: Call the agent's health endpoint
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{agent_url}/health")
        
        return {
            "status_code": response.status_code,
            "passed": response.status_code == 200,
            "response": response.json()
        }
```

### Example 2: Create rule with custom code
```bash
curl -X POST http://localhost:8000/api/rules \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Custom Evaluation",
    "description": "Custom rule with specific logic",
    "code_content": "async def evaluate(agent_url, auth_config, config):\n    import httpx\n    async with httpx.AsyncClient() as client:\n        # Your custom logic here\n        response = await client.post(f\"{agent_url}/execute\", json={\"input_data\": config})\n        return {\"result\": response.json(), \"passed\": True}\n"
  }'
```

### Example 3: Complete workflow with default rule
```bash
# 1. Create rule (uses default code)
RULE_RESPONSE=$(curl -s -X POST http://localhost:8000/api/rules \
  -H "Content-Type: application/json" \
  -d '{"name": "Quick Test", "description": "Quick health check"}')

RULE_ID=$(echo $RULE_RESPONSE | python3 -c "import sys, json; print(json.load(sys.stdin)['id'])")
echo "Created rule: $RULE_ID"

# 2. Create job
JOB_RESPONSE=$(curl -s -X POST http://localhost:8000/api/jobs \
  -H "Content-Type: application/json" \
  -d "{\"rule_id\": \"$RULE_ID\", \"agent_id\": \"YOUR_AGENT_ID\", \"config_overrides\": {}}")

JOB_ID=$(echo $JOB_RESPONSE | python3 -c "import sys, json; print(json.load(sys.stdin)['id'])")
echo "Created job: $JOB_ID"

# 3. Execute job
curl -X POST http://localhost:8000/api/jobs/$JOB_ID/execute | python3 -m json.tool
```

## Benefits
- ✅ **No need to remember function signature** - The default provides the correct template
- ✅ **Working example** - The default code actually works against the sample agent
- ✅ **Documented parameters** - Clear docstring explaining each parameter
- ✅ **Easy to customize** - You can still provide your own code when needed
