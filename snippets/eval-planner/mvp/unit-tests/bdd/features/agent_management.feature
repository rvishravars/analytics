Feature: Agent Management
  As an Eval Engineer
  I want to manage the registry of agents
  So that I can use them for evaluations

  Scenario: Register a new agent
    When I register an agent named "Production API" with URL "http://prod:8080"
    Then the agent should be registered successfully
    And I should see "Production API" in the agent registry

  Scenario: List all agents
    Given an Agent named "Staging Bot" with URL "http://staging:8080"
    And an Agent named "Dev Bot" with URL "http://dev:8080"
    When I list all registered agents
    Then I should find "Staging Bot" and "Dev Bot" in the list

  Scenario: Get agent details
    Given an Agent named "Detailed Bot" with URL "http://details:8080"
    When I request details for "Detailed Bot"
    Then I should receive the correct URL "http://details:8080"
