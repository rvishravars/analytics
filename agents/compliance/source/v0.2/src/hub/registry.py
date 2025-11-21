from typing import Dict, Any, Optional
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("AgentHub")

class AgentHub:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(AgentHub, cls).__new__(cls)
            cls._instance.agents: Dict[str, Any] = {}
        return cls._instance

    def register_agent(self, agent_name: str, agent_instance: Any):
        """Registers an agent to the hub."""
        if agent_name in self.agents:
            logger.warning(f"Agent {agent_name} is already registered. Overwriting.")
        
        self.agents[agent_name] = agent_instance
        logger.info(f"Agent registered: {agent_name}")

    def get_agent(self, agent_name: str) -> Optional[Any]:
        """Retrieves an agent by name."""
        return self.agents.get(agent_name)

    def list_agents(self) -> list[str]:
        """Lists all registered agent names."""
        return list(self.agents.keys())

# Global instance
hub = AgentHub()
