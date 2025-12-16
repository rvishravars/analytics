import logging
import asyncio
import sys
from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from src.hub.registry import hub
from src.agents.compliance import ComplianceAgent
from src.agents.example import ExampleAgent

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("Main")

async def main():
    logger.info("Starting v0.2.1 Agent System (Real MCP)...")

    # 1. Initialize Compliance Agent (needed by the server process, but we are in the client process here)
    # WAIT: The server runs in a separate process. It needs its own Compliance Agent instance.
    # The Hub is in-memory. If we split processes, they won't share the Hub!
    # CHALLENGE: 'Real' MCP implies distributed systems.
    # SOLUTION: 
    # The 'Server' process will load the Compliance Agent.
    # The 'Client' process (this one) will run the Example Agent.
    # We need to make sure `src/mcp/server.py` initializes what it needs.

    # 2. Initialize Worker Agent (Client side)
    worker = ExampleAgent()

    # 3. Connect to MCP Server via Stdio
    # We assume the server is at src/mcp/server.py relative to this file
    import os
    
    # Get the directory containing main.py
    base_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Construct path to server.py
    server_script = os.path.join(base_dir, "src", "mcp", "server.py")
    
    env = os.environ.copy()
    # Set PYTHONPATH to the base directory so imports work
    env["PYTHONPATH"] = base_dir
    
    server_params = StdioServerParameters(
        command=sys.executable,
        args=[server_script],
        env=env
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            # Initialize the session
            await session.initialize()
            
            # Inject session into worker
            worker.set_mcp_session(session)

            # 4. Run Worker Agent
            await worker.run()

    logger.info("System shutdown.")

if __name__ == "__main__":
    asyncio.run(main())
