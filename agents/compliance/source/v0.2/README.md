# Agent Hub (v0.2)

This project implements a secure Agent Hub architecture with a centralized Gateway (MCP Server) and a Compliance Agent.

## Architecture

-   **Agent Hub**: Central registry for all agents.
-   **MCP Server**: The only gateway for external API calls.
-   **Compliance Agent**: Monitors and enforces security policies on all traffic.

## Directory Structure

-   `src/hub`: Registry implementation.
-   `src/mcp`: Gateway server implementation.
-   `src/agents`: Agent implementations (Compliance, Base, Example).
-   `main.py`: Entry point.

## How to Run with Docker

### Prerequisites
-   Docker installed.

### Build
Run the following command from the `source/v0.2` directory:
```bash
docker build -t agent-hub-v0.2 .
```

### Run
```bash
docker run agent-hub-v0.2
```

### Expected Output
You should see logs indicating:
1.  Agents registering.
2.  A valid external call succeeding.
3.  A blocked external call (to `unsafe.com`) failing with a Compliance warning.

Example:
```
INFO:ExampleAgent:Attempting valid call...
INFO:ExampleAgent:Valid call success: ...
INFO:ExampleAgent:Attempting blocked call...
WARNING:ComplianceAgent:[Compliance Block] Access to unsafe.com is denied.
```

## Local Development
To run locally without Docker:
```bash
pip install -r requirements.txt
python main.py
```
