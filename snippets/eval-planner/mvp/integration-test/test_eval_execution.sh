#!/bin/bash
# Test script for eval execution

API_BASE="http://localhost:8000/api"
TS=$(date +%s)

echo "=== Testing Eval Execution Workflow ==="
echo ""

# Step 1: Create a test evaluation rule
echo "1. Creating test evaluation rule..."
cat <<EOF > rule_payload.json
{
    "name": "Health Check Test $TS",
    "description": "Simple health check evaluation",
    "code_content": "async def evaluate(agent_url, auth_config, config):\n    import httpx\n    async with httpx.AsyncClient() as client:\n        response = await client.get(f\"{agent_url}/health\")\n        return {\"status_code\": response.status_code, \"body\": response.json()}\n",
    "rule_type": "PYTHON"
}
EOF

RULE_RESPONSE=$(curl -s -X POST "$API_BASE/rules" \
  -H "Content-Type: application/json" \
  -d @rule_payload.json)

RULE_ID=$(echo "$RULE_RESPONSE" | jq -r '.id' | grep -v null)
if [ -z "$RULE_ID" ]; then
    echo "❌ Failed to create rule. Response:"
    echo "$RULE_RESPONSE" | jq .
    exit 1
fi
echo "Created rule with ID: $RULE_ID"
echo ""

# Step 2: Register the sample agent
echo "2. Registering sample agent..."
cat <<EOF > agent_payload.json
{
    "name": "Sample Test Agent $TS",
    "url": "http://sample-agent-container:8081",
    "auth_config": {}
}
EOF

AGENT_RESPONSE=$(curl -s -X POST "$API_BASE/agents" \
  -H "Content-Type: application/json" \
  -d @agent_payload.json)

AGENT_ID=$(echo "$AGENT_RESPONSE" | jq -r '.id' | grep -v null)
if [ -z "$AGENT_ID" ]; then
    echo "❌ Failed to register agent. Response:"
    echo "$AGENT_RESPONSE" | jq .
    exit 1
fi
echo "Registered agent with ID: $AGENT_ID"
echo ""

# Step 3: Create a job
echo "3. Creating job..."
cat <<EOF > job_payload.json
{
    "rule_id": "$RULE_ID",
    "agent_id": "$AGENT_ID",
    "config_overrides": {}
}
EOF

JOB_RESPONSE=$(curl -s -X POST "$API_BASE/jobs" \
  -H "Content-Type: application/json" \
  -d @job_payload.json)

JOB_ID=$(echo "$JOB_RESPONSE" | jq -r '.id' | grep -v null)
if [ -z "$JOB_ID" ]; then
    echo "❌ Failed to create job. Response:"
    echo "$JOB_RESPONSE" | jq .
    exit 1
fi
echo "Created job with ID: $JOB_ID"
echo ""

# Step 4: Execute the job (Optional in MVP since creation triggers it, but we can call it)
echo "4. Executing job..."
EXEC_RESPONSE=$(curl -s -X POST "$API_BASE/jobs/$JOB_ID/execute")
echo "Execution triggered. Response:"
echo "$EXEC_RESPONSE" | jq .
echo ""

# Step 5: Get job result (Poll for a few seconds if needed)
echo "5. Fetching job result..."
for i in {1..5}; do
    RESULT_RESPONSE=$(curl -s -X GET "$API_BASE/jobs/$JOB_ID/result")
    STATUS=$(echo "$RESULT_RESPONSE" | jq -r '.status' | grep -v null)
    if [ "$STATUS" = "SUCCESS" ] || [ "$STATUS" = "FAILED" ]; then
        break
    fi
    echo "Waiting for result... ($i/5)"
    sleep 2
done

echo "Result:"
echo "$RESULT_RESPONSE" | jq .
echo ""

echo "=== Test Complete ==="
rm -f rule_payload.json agent_payload.json job_payload.json
