import socket
import ssl
import requests
import sys
from urllib.parse import urlparse

import os

TARGET_URL = os.getenv("TARGET_URL", "https://localhost:8000/secure-data")

def check_tls_version(url):
    print(f"[*] Checking TLS version for {url}...")
    parsed = urlparse(url)
    hostname = parsed.hostname
    port = parsed.port or 443

    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE

    try:
        with socket.create_connection((hostname, port)) as sock:
            with context.wrap_socket(sock, server_hostname=hostname) as ssock:
                version = ssock.version()
                cipher = ssock.cipher()
                print(f"    Detected Protocol: {version}")
                print(f"    Detected Cipher: {cipher}")

                if version in ["TLSv1.2", "TLSv1.3"]:
                    print("    [PASS] Encrypted Transport Validation: TLS version is 1.2 or higher.")
                    return True
                else:
                    print(f"    [FAIL] Encrypted Transport Validation: TLS version is {version} (Expected 1.2+).")
                    return False
    except Exception as e:
        print(f"    [FAIL] Encrypted Transport Validation: Could not connect or handshake failed. Error: {e}")
        return False

def check_authentication(url):
    print(f"\n[*] Checking Authentication Enforcement for {url}...")
    try:
        # Suppress warnings for self-signed certs
        requests.packages.urllib3.disable_warnings()
        
        response = requests.get(url, verify=False)
        print(f"DEBUG: Auth check status code: {response.status_code}")
        if response.status_code in [401, 403]:
            print("    [PASS] Authentication Enforcement: API requires authentication (returned 401/403).")
            return True
        else:
            print(f"    [FAIL] Authentication Enforcement: API returned {response.status_code} (Expected 401/403).")
            return False
    except Exception as e:
        print(f"DEBUG: Auth check exception: {e}")
        print(f"    [FAIL] Authentication Enforcement: Request failed. Error: {e}")
        return False

def main():
    print("=== HIPAA Compliance Agent ===\n")
    
    tls_pass = check_tls_version(TARGET_URL)
    auth_pass = check_authentication(TARGET_URL)

    print("\n=== Summary ===")
    if tls_pass and auth_pass:
        print("OVERALL STATUS: COMPLIANT")
        sys.exit(0)
    else:
        print("OVERALL STATUS: NON-COMPLIANT")
        sys.exit(1)

if __name__ == "__main__":
    main()
