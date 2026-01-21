#!/bin/bash
# Remove existing container if it exists
docker rm -f sample-agent-container 2>/dev/null || true

# Run the container attached to the evaluation network
docker run -d --name sample-agent-container -p 8081:8081 --network eval-planner-network sample-agent:latest

echo "Sample agent is running on http://localhost:8081"
