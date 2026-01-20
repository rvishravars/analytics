#!/bin/bash

# Navigate to the directory containing the script
cd "$(dirname "$0")"

echo "🛑 Stopping Agentic Eval MVP..."

# Stop containers and remove network
docker compose down

echo "✅ Undeploy Complete!"
echo "   (Note: Data volumes were preserved. To remove data, run: docker compose down -v)"
