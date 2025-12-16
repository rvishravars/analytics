Feature: HIPAA Compliance and Secure Gateway
  As a Healthcare System Administrator
  I want to ensure all external communication is secure and monitored
  So that I can comply with HIPAA regulations and protect patient data

  Background:
    Given the Agent Hub is running
    And the MCP Server Gateway is active
    And the Compliance Agent is registered and monitoring

  Scenario: Agent Registration
    Given a new agent named "billing_agent_01"
    When the agent starts up
    Then it should automatically register with the Agent Hub
    And it should be listed in the active agents registry

  Scenario: Successful Secure External Call
    Given "billing_agent_01" is registered
    And the target URL is "https://www.google.com"
    And the target server supports TLS 1.2 or higher
    When "billing_agent_01" requests "GET" on the target URL via the MCP Gateway
    Then the Compliance Agent should inspect the request
    And the Compliance Agent should allow the request
    And the MCP Gateway should execute the call
    And the response status code should be 200

  Scenario: Blocked Insecure HTTP Call
    Given "billing_agent_01" is registered
    And the target URL is "http://neverssl.com"
    And the target server uses unencrypted HTTP
    When "billing_agent_01" requests "GET" on the target URL via the MCP Gateway
    Then the Compliance Agent should inspect the request
    And the Compliance Agent should block the request
    And the MCP Gateway should return a 403 Forbidden error
    And a security warning should be logged

  Scenario: Blocked Outdated TLS Call
    Given "billing_agent_01" is registered
    And the target URL is "https://tls-v1-0.badssl.com:1010"
    And the target server only supports TLS 1.0 or 1.1
    When "billing_agent_01" requests "GET" on the target URL via the MCP Gateway
    Then the Compliance Agent should inspect the request
    And the Compliance Agent should detect the outdated TLS version
    And the Compliance Agent should block the request
    And the MCP Gateway should return a 403 Forbidden error
