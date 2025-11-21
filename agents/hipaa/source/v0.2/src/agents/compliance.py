import logging
import ssl
import socket
from urllib.parse import urlparse
from .base import BaseAgent

logger = logging.getLogger("ComplianceAgent")

class ComplianceAgent(BaseAgent):
    def __init__(self):
        super().__init__(name="compliance_agent")

    def run(self):
        logger.info("Compliance Agent is running and monitoring.")

    def check_ssl_protocol(self, hostname: str, port: int = 443) -> bool:
        """
        Checks if the server supports TLS 1.2 or higher.
        Returns True if compliant, False otherwise.
        """
        context = ssl.create_default_context()
        try:
            with socket.create_connection((hostname, port), timeout=5) as sock:
                with context.wrap_socket(sock, server_hostname=hostname) as ssock:
                    version = ssock.version()
                    logger.info(f"SSL/TLS Version for {hostname}: {version}")
                    
                    # Check version
                    if version in ["TLSv1.2", "TLSv1.3"]:
                        return True
                    else:
                        logger.warning(f"Non-compliant TLS version: {version}")
                        return False
        except Exception as e:
            logger.error(f"SSL Check failed for {hostname}: {e}")
            return False

    def inspect_request(self, caller_id: str, target_url: str, method: str, data: dict) -> bool:
        """
        Inspects an outgoing request.
        Returns True if allowed, False if blocked.
        """
        logger.info(f"[Compliance Check] Request from {caller_id} to {target_url}")
        
        parsed = urlparse(target_url)
        hostname = parsed.hostname
        port = parsed.port or (443 if parsed.scheme == "https" else 80)

        # Allow internal mocks or localhost for testing
        if hostname in ["mock-api.com", "localhost", "127.0.0.1"]:
            return True
            
        if parsed.scheme != "https":
            logger.warning(f"[Compliance Block] Non-HTTPS traffic to {hostname} is denied.")
            return False

        # Perform Real TLS Check
        if not self.check_ssl_protocol(hostname, port):
            logger.warning(f"[Compliance Block] {hostname} does not support TLS 1.2+")
            return False
        
        return True

    def inspect_response(self, caller_id: str, target_url: str, response_data: dict):
        """
        Inspects an incoming response.
        """
        logger.info(f"[Compliance Check] Response for {caller_id} from {target_url}")
        # In a real scenario, we might check for DLP (Data Loss Prevention) here.
        pass
