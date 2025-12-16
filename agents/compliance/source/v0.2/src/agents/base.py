import logging
import asyncio
from abc import ABC, abstractmethod
from ..hub.registry import hub

logger = logging.getLogger("BaseAgent")

class BaseAgent(ABC):
    def __init__(self, name: str):
        self.name = name
        self.register()
        self.mcp_session = None # Will be injected by main.py for this demo

    def register(self):
        """Registers the agent with the central hub."""
        hub.register_agent(self.name, self)

    def set_mcp_session(self, session):
        """Injects the MCP Client Session."""
        self.mcp_session = session

    async def call_external(self, target_url: str, method: str = "GET", data: dict = None):
        """
        Makes an external API call via the MCP Server Gateway using the MCP Protocol.
        """
        if not self.mcp_session:
            logger.error("MCP Session not available! Cannot make external call.")
            raise RuntimeError("MCP Session unavailable")
        
        # Call the 'fetch' tool exposed by the MCP Server
        result = await self.mcp_session.call_tool(
            "fetch",
            arguments={
                "caller_agent_id": self.name,
                "target_url": target_url,
                "method": method,
                "data": data or {}
            }
        )
        
        # Parse the result (MCP returns a list of content)
        # We expect the tool to return a JSON string or similar, but FastMCP tools return what we return.
        # However, the SDK wraps it. Let's inspect the result structure in the demo.
        # Usually result.content is a list of TextContent or ImageContent.
        
        # For FastMCP, if we return a dict, it might be serialized to JSON text.
        # Let's assume we get TextContent back.
        
        if result.content and hasattr(result.content[0], "text"):
             import json
             try:
                 return json.loads(result.content[0].text)
             except:
                 return result.content[0].text
        
        return result

    @abstractmethod
    async def run(self):
        """Main agent logic (Async)."""
        pass
