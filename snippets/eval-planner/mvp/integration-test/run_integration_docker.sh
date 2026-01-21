#!/bin/bash
# Script to run integration tests in a container

# Build from the mvp root
cd "$(dirname "$0")/.."

echo "🏗 Building integration test image..."
sudo docker build -t eval-integration-test -f integration-test/Dockerfile.integration .

echo "🧪 Running integration tests..."
# We use the source_default network created by docker-compose
# and point to the 'api' service.
sudo docker run --rm --network source_default -e API_URL="http://api:8000/api" eval-integration-test
