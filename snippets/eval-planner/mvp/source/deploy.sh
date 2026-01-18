#!/bin/bash

echo "🚀 Starting Agentic Eval MVP Deployment..."

# Check if docker is installed
if ! command -v docker &> /dev/null; then
    echo "Error: Docker is not installed."
    exit 1
fi

echo "📦 Building and Starting Services..."
docker compose up -d --build

echo "✅ Deployment Complete!"
echo "   - Dashboard: http://localhost:3000"
echo "   - API Docs:  http://localhost:8000/docs"
