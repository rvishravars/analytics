#!/bin/bash
# Script to run BDD tests in a container

# Build from the mvp root
cd "$(dirname "$0")/../.."

echo "🏗 Building BDD test image..."
sudo docker build -t eval-bdd-tests -f unit-tests/bdd/Dockerfile.bdd .

echo "🧪 Running BDD tests..."
sudo docker run --rm eval-bdd-tests
