#!/bin/bash
# Test script for eval execution

API_BASE="http://localhost:8000/api"
TS=$(date +%s)

echo "=== Testing Eval Execution Workflow ==="
echo ""

# Step 1: Create a test evaluation rule
echo "1. Creating test evaluation rule..."
RULE_RESPONSE=$(curl -s -X POST "$API_BASE/rules" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Health Check Test $TS",
    "description": "Simple health check evaluation",
    "code_content": "async def evaluate(agent_url, auth_config, config):\n    import httpx\n    async with httpx.AsyncClient() as client:\n        response = await client.get(f\"{agent_url}/health\")\n        return {\"status_code\": response.status_code, \"body\": response.json()}\n",
    "rule_type": "PYTHON"
  }')

RULE_ID=$(echo $RULE_RESPONSE | jq -r '.id' | grep -v null)
echo "Created rule with ID: $RULE_ID"
echo ""

# Step 2: Register the sample agent (using container name on shared network)
echo "2. Registering sample agent..."
AGENT_RESPONSE=$(curl -s -X POST "$API_BASE/agents" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Sample Test Agent $TS",
    "url": "http://sample-agent-container:8081",
    "auth_config": {}
  }')

AGENT_ID=$(echo $AGENT_RESPONSE | jq -r '.id' | grep -v null)
echo "Registered agent with ID: $AGENT_ID"
echo ""

# Step 3: Create a job
echo "3. Creating job..."
JOB_RESPONSE=$(curl -s -X POST "$API_BASE/jobs" \
  -H "Content-Type: application/json" \
  -d "{
    \"rule_id\": \"$RULE_ID\",
    \"agent_id\": \"$AGENT_ID\",
    \"config_overrides\": {}
  }")

JOB_ID=$(echo $JOB_RESPONSE | jq -r '.id' | grep -v null)
echo "Created job with ID: $JOB_ID"
echo ""

# Step 4: Execute the job
echo "4. Executing job..."
EXEC_RESPONSE=$(curl -s -X POST "$API_BASE/jobs/$JOB_ID/execute")
echo "Execution result:"
echo $EXEC_RESPONSE | python3 -m json.tool
echo ""

# Step 5: Get job result
echo "5. Fetching job result..."
RESULT_RESPONSE=$(curl -s -X GET "$API_BASE/jobs/$JOB_ID/result")
echo "Result:"
echo $RESULT_RESPONSE | python3 -m json.tool
echo ""

echo "=== Test Complete ==="
