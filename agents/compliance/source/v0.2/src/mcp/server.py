import logging
import requests
from mcp.server.fastmcp import FastMCP
from src.hub.registry import hub
from src.agents.compliance import ComplianceAgent


# Configure logging for the server process
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("MCPServer")

# Initialize FastMCP
mcp = FastMCP("Gateway")

def get_compliance_agent():
    """Helper to retrieve the compliance agent from the hub."""
    agent = hub.get_agent("compliance_agent")
    if not agent:
        # In the server process, we need to make sure it's registered.
        # If this is a fresh process, the Hub is empty!
        # So we must instantiate it here.
        logger.info("Initializing Compliance Agent in Server Process...")
        agent = ComplianceAgent()
    return agent

@mcp.tool()
def fetch(caller_agent_id: str, target_url: str, method: str = "GET", data: dict = None) -> str:
    """
    Executes an external API call via the Gateway, subject to compliance checks.
    Returns a JSON string result.
    """
    logger.info(f"Received external call request from {caller_agent_id} to {target_url}")

    # 1. Get Compliance Agent
    compliance_agent = get_compliance_agent()

    # 2. Pre-flight Compliance Check
    allowed = compliance_agent.inspect_request(caller_agent_id, target_url, method, data)
    if not allowed:
        logger.warning(f"Request blocked by Compliance Agent: {target_url}")
        return '{"error": "Request blocked by Compliance Policy", "status_code": 403}'

    # 3. Execute External Call
    try:
        if "mock-api" in target_url:
            response_data = {"status": "success", "data": "mocked_response"}
            status_code = 200
        else:
            if method.upper() == "GET":
                resp = requests.get(target_url, params=data)
            elif method.upper() == "POST":
                resp = requests.post(target_url, json=data)
            else:
                resp = requests.request(method, target_url, json=data)
            
            response_data = resp.json() if resp.content else {}
            status_code = resp.status_code

    except Exception as e:
        logger.error(f"External call failed: {e}")
        return f'{{"error": "{str(e)}", "status_code": 500}}'

    # 4. Post-flight Compliance Check
    compliance_agent.inspect_response(caller_agent_id, target_url, response_data)

    import json
    return json.dumps({"status_code": status_code, "body": response_data})

if __name__ == "__main__":
    # Run the server
    mcp.run()
