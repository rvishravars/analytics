import logging
from .base import BaseAgent

logger = logging.getLogger("ExampleAgent")

class ExampleAgent(BaseAgent):
    def __init__(self):
        super().__init__(name="billing_agent_01")

    async def run(self):
        logger.info("Example Agent starting work...")
        
        # 1. Try a valid call (Mock)
        try:
            logger.info("Attempting valid call (Mock)...")
            response = await self.call_external("https://mock-api.com/invoice", method="GET")
            logger.info(f"Valid call success: {response}")
        except Exception as e:
            logger.error(f"Valid call failed: {e}")

        # 2. Try a valid real call (Google - TLS 1.3)
        try:
            logger.info("Attempting valid real call (google.com)...")
            # We use HEAD to avoid downloading large content
            response = await self.call_external("https://www.google.com", method="GET")
            logger.info(f"Real call success: {response.get('status_code')}")
        except Exception as e:
            logger.error(f"Real call failed: {e}")

        # 3. Try a blocked call (HTTP site)
        try:
            logger.info("Attempting blocked call (neverssl.com - HTTP)...")
            await self.call_external("http://neverssl.com", method="GET")
        except Exception as e:
            logger.info(f"Blocked call failed as expected: {e}")

        # 4. Try a blocked call (Bad SSL - TLS 1.0)
        # Note: badssl.com might be slow or flaky, but good for testing.
        try:
            logger.info("Attempting blocked call (tls-v1-0.badssl.com)...")
            await self.call_external("https://tls-v1-0.badssl.com:1010", method="GET")
        except Exception as e:
            logger.info(f"Blocked call failed as expected: {e}")
